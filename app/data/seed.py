"""Database seeding pipeline: generate -> validate -> persist -> infer."""
from __future__ import annotations

import json
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.analytics.features import BaselineStore, compute_features
from app.analytics.inference import TwinInference
from app.analytics.propagation import build_chains_from_telemetry
from app.analytics.recommendations import recommend_all
from app.config.plant_config import (PRODUCTION_HOURS_PER_DAY, SEED_DEFAULT,
                                     build_station_specs, production_anchor)
from app.data import database as db
from app.simulation.line import LineSimulator
from app.simulation.scenarios import build_plan, get_scenario
from app.simulation.sensors import TelemetryBuilder, plan_random_outages


def generate_history(specs: pd.DataFrame, start: datetime, end: datetime,
                     target_rate_vph: float, seed: int,
                     plan=None, vehicle_offset: int = 0):
    sim = LineSimulator(specs, seed=seed)
    run = sim.run(start, end, target_rate_vph=target_rate_vph, plan=plan,
                  vehicle_offset=vehicle_offset)
    outages = plan_random_outages(specs, start, end, seed)
    tb = TelemetryBuilder(specs, seed=seed, outages=outages)
    if plan is not None:
        tb.add_outages(plan.outage_windows)
    tel = tb.build(run.visits, plan)
    return run.visits, tel, run.vehicles


def compute_twin_artifacts(conn) -> dict:
    """Features + inference over the live window; persists metrics/alerts/etc."""
    specs = db.load_stations(conn)
    if specs.empty:
        return {"ok": False, "reason": "no stations in database"}
    from app.simulation.plant import PlantModel
    plant = PlantModel(specs)

    max_ts_row = conn.execute("SELECT MAX(ts) FROM telemetry").fetchone()[0]
    if not max_ts_row:
        return {"ok": False, "reason": "no telemetry"}
    anchor = pd.Timestamp(max_ts_row)

    ref_start = anchor - pd.Timedelta(hours=40)
    ref_end = anchor - pd.Timedelta(hours=16)
    live_start = anchor - pd.Timedelta(hours=24)

    tel_ref = db.load_telemetry(conn, str(ref_start), str(ref_end))
    tel_live = db.load_telemetry(conn, str(live_start), str(anchor + pd.Timedelta(seconds=1)))
    if tel_live.empty:
        return {"ok": False, "reason": "no live telemetry"}

    baseline = BaselineStore(tel_ref)
    feat_hist, _ = compute_features(tel_live, specs, plant, baseline)
    if feat_hist.empty:
        return {"ok": False, "reason": "feature computation produced no rows"}

    engine = TwinInference(specs, plant)
    try:
        hist_part = feat_hist[feat_hist.index.get_level_values("bucket_ts")
                              < feat_hist.index.get_level_values("bucket_ts").max()
                              - pd.Timedelta(minutes=90)]
        if len(hist_part) >= 80:
            engine.fit(hist_part)
    except Exception:
        pass
    states = engine.update(feat_hist)
    if not states:
        return {"ok": False, "reason": "inference produced no states"}

    met_rows = []
    state_by_station = {s.station_id: s for s in states}
    for (bts, sid), row in feat_hist.iterrows():
        st = state_by_station.get(sid)
        scored = st is not None and str(bts) == st.bucket_ts
        met_rows.append({
            "bucket_ts": str(bts), "station_id": sid,
            "throughput_vph": float(row.get("throughput_vph", 0)),
            "avg_cycle_time": float(row.get("avg_cycle_time", 0)),
            "ct_deviation_pct": float(row.get("ct_deviation_pct", 0)),
            "queue_length": float(row.get("queue_growth", 0)),
            "queue_pressure": float(row.get("queue_pressure", 0)),
            "starvation_rate": float(row.get("starvation_freq", 0)),
            "blocking_rate": float(row.get("blocking_freq", 0)),
            "defect_rate": float(row.get("defect_rate", 0)),
            "sensor_coverage": (st.sensor_coverage if scored
                                else float(row.get("sensor_coverage_obs", 0))),
            "health_score": st.health_score if scored else np.nan,
            "anomaly_score": st.anomaly_score if scored else np.nan,
            "bottleneck_score": st.bottleneck_score if scored else np.nan,
            "bottleneck_prob": st.bottleneck_prob if scored else np.nan,
            "confidence": st.confidence if scored else np.nan,
            "status": st.status if scored else "",
            "causes_json": json.dumps(st.causes[:3]) if scored else "[]",
            "explanation_json": json.dumps(st.explanation) if scored else "[]",
        })
    db.insert_metrics(conn, pd.DataFrame(met_rows))
    conn.execute("DELETE FROM station_metrics WHERE bucket_ts < ?",
                 (str(live_start),))
    conn.commit()

    latest_states = sorted(states, key=lambda s: s.bucket_ts)
    now = latest_states[-1].bucket_ts
    alerts = []
    latest = {s.station_id: s for s in states}
    for sid, s in sorted(latest.items(), key=lambda kv: kv[1].health_score):
        cov_txt = f"{s.sensor_coverage:.0%}"
        conf_txt = f"{s.confidence:.0f}%"
        if s.health_score < 40:
            sev, kind = "CRITICAL", ("root_cause" if s.is_root_cause_candidate
                                     else "station_critical")
            msg = (f"Predicted bottleneck ({s.bottleneck_prob:.0%})" 
                   if s.bottleneck_prob > 0.5 else "Station critical")
        elif s.health_score < 60:
            sev, kind = "WARNING", "degraded"
            msg = "Station degraded"
        elif s.health_score < 80:
            sev, kind = "INFO", "watch"
            msg = "Watch: early drift detected"
        else:
            continue
        alerts.append({
            "alert_id": f"AL-{now.replace(' ', 'T').replace(':', '')}-{sid}",
            "ts": now, "station_id": sid, "severity": sev, "kind": kind,
            "message": f"{msg} | Confidence {conf_txt} | Sensor coverage {cov_txt}",
            "confidence": round(s.confidence / 100.0, 2),
            "sensor_coverage": round(s.sensor_coverage, 2),
            "causes": s.causes, "active": 1})
    db.deactivate_alerts(conn)
    db.insert_alerts(conn, alerts)

    defects = build_chains_from_telemetry(
        tel_live[tel_live["ts"] >= str(anchor - pd.Timedelta(hours=8))],
        plant, seed=int(db.get_meta(conn, "seed", SEED_DEFAULT)))
    if defects:
        scen = db.get_meta(conn, "active_scenario", "")
        for d in defects:
            d["scenario"] = scen
        db.insert_defects(conn, defects)

    recs = recommend_all(list(latest.values()))
    if recs:
        db.insert_recommendations(conn, recs)

    return {"ok": True, "anchor": str(anchor), "states": states,
            "alerts": alerts, "defects": defects, "recommendations": recs}


def seed_database(days: float = 7, vehicles_target: int = 2400, seed: int = SEED_DEFAULT,
                  db_path=None, scenario: str = "normal",
                  rate_vph: float | None = None) -> dict:
    specs = build_station_specs(seed)
    conn = db.get_conn(db_path)
    db.init_db(conn)
    for t in ("stations", "vehicles", "telemetry", "station_metrics", "alerts",
              "defects", "recommendations", "simulation_runs"):
        conn.execute(f"DELETE FROM {t}")
    conn.commit()
    db.insert_stations(conn, specs)

    anchor = production_anchor()
    start = anchor - timedelta(days=days)
    derived_rate = vehicles_target / max(days * PRODUCTION_HOURS_PER_DAY, 1)
    rate = float(rate_vph) if rate_vph else max(6.0, derived_rate)

    scen = get_scenario(scenario)
    plan = build_plan(scen, anchor, seed) if scenario != "normal" else None
    visits, tel, veh = generate_history(specs, start, anchor, rate, seed, plan=plan)

    db.insert_telemetry(conn, tel)
    db.insert_vehicles(conn, veh)
    db.set_meta(conn, "anchor_end", anchor.strftime("%Y-%m-%d %H:%M:%S"))
    db.set_meta(conn, "seed", seed)
    db.set_meta(conn, "days", days)
    db.set_meta(conn, "target_vehicles", len(veh))
    db.set_meta(conn, "rate_vph", round(rate, 2))
    db.set_meta(conn, "active_scenario", scenario)
    db.set_meta(conn, "vehicles_counter", len(veh))
    db.set_meta(conn, "generated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    result = compute_twin_artifacts(conn)
    n_tel = db.count_table(conn, "telemetry")
    conn.close()
    result.update({"stations": len(specs), "telemetry_rows": n_tel,
                   "vehicles": len(veh)})
    return result
