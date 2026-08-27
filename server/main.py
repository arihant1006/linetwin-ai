"""LineTwin.ai local API server.

Thin FastAPI wrapper exposing the existing, tested simulation + analytics
pipeline over JSON. Run from the repo root:

    .venv/bin/uvicorn server.main:app --port 8000

Everything is local: SQLite persistence (data/digitaltwin.db, override with
DIGITALTWIN_DB), no external services. CORS is enabled for the Next.js dev
server on localhost:3000.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contextlib import closing

from app.analytics.health import compute_confidence
from app.analytics.propagation import sankey_edges
from app.analytics.whatif import ACTIONS, PLCAdapter, simulate_action
from app.config.plant_config import SEED_DEFAULT, status_band
from app.data import database as db
from app.simulation.inject import apply_scenario, reset_simulation
from app.simulation.scenarios import all_scenarios

app = FastAPI(title="LineTwin.ai API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# A single writer lock: scenario injection / reset are expensive, non-
# interruptible operations that rewrite telemetry + recompute artifacts.
_sim_lock = threading.Lock()


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _conn() -> Any:
    conn = db.get_conn()
    db.init_db(conn)  # additive migration guard (explanation_json etc.)
    return conn


def _records(df: pd.DataFrame) -> list[dict]:
    if df is None or df.empty:
        return []
    out = json.loads(df.to_json(orient="records"))
    return out


def _loads(raw: Any, default):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _scenario_dict(s) -> dict:
    return {
        "key": s.key,
        "label": s.label,
        "description": s.description,
        "target_station": s.target_station,
        "defect_chain": list(s.defect_chain),
        "window_hours": s.window_hours,
        "severity": s.severity,
    }


# --------------------------------------------------------------------------
# read routes
# --------------------------------------------------------------------------

@app.get("/api/meta")
def get_meta() -> dict:
    with closing(_conn()) as conn:
        met = db.load_latest_metrics(conn)
        return {
            "active_scenario": str(db.get_meta(conn, "active_scenario", "normal")),
            "sim_clock": str(met["bucket_ts"].max()) if not met.empty else None,
            "seed": int(db.get_meta(conn, "seed", SEED_DEFAULT)),
            "counts": {
                "vehicles": db.count_table(conn, "vehicles"),
                "telemetry": db.count_table(conn, "telemetry"),
            },
            "generated_at": db.get_meta(conn, "generated_at"),
            "has_data": db.count_table(conn, "stations") > 0
                        and db.count_table(conn, "telemetry") > 0,
        }


@app.get("/api/stations")
def get_stations() -> list[dict]:
    with closing(_conn()) as conn:
        df = db.load_stations(conn)
    return _records(df.reset_index()) if not df.empty else []


@app.get("/api/metrics/latest")
def get_latest_metrics() -> list[dict]:
    with closing(_conn()) as conn:
        df = db.load_latest_metrics(conn)
    recs = _records(df)
    for r in recs:
        r["causes"] = _loads(r.pop("causes_json", None), [])
        r["explanation"] = _loads(r.pop("explanation_json", None), [])
        r.pop("index", None)
    return recs


@app.get("/api/metrics/history")
def get_metric_history(hours: float = 168.0) -> list[dict]:
    hours = min(max(hours, 1.0), 24 * 30)
    with closing(_conn()) as conn:
        df = db.load_metric_history(conn, hours=hours)
    return _records(df)


@app.get("/api/stations/{station_id}/telemetry")
def get_station_telemetry(station_id: str, limit: int = 200) -> list[dict]:
    limit = min(max(limit, 10), 2000)
    with closing(_conn()) as conn:
        tel = db.load_telemetry(conn, station_ids=[station_id])
    if tel.empty:
        return []
    return _records(tel.tail(limit))


@app.get("/api/alerts")
def get_alerts(active_only: bool = True, limit: int = 100) -> list[dict]:
    limit = min(max(limit, 1), 500)
    with closing(_conn()) as conn:
        df = db.load_alerts(conn, active_only=active_only, limit=limit)
    recs = _records(df)
    for r in recs:
        r["causes"] = _loads(r.pop("causes_json", None), [])
    return recs


@app.get("/api/defects")
def get_defects(limit: int = 200) -> dict:
    limit = min(max(limit, 1), 1000)
    with closing(_conn()) as conn:
        df = db.load_defects(conn, limit=limit)
    recs = _records(df)
    chains = []
    for d in recs:
        aff = _loads(d.get("affected_stations_json"), [])
        if aff:
            chains.append({"affected_stations": list(aff),
                           "detected_station": d.get("detected_station")})
    edges = [{"source": a, "target": b, "value": n} for a, b, n in sankey_edges(chains)]
    return {"defects": recs, "sankey_edges": edges}


@app.get("/api/recommendations")
def get_recommendations(limit: int = 100) -> list[dict]:
    limit = min(max(limit, 1), 500)
    with closing(_conn()) as conn:
        df = db.load_recommendations(conn, limit=limit)
    recs = _records(df)
    # One open recommendation per station: repeated inference runs append new
    # rows for the same station/issue, so keep only the newest per station.
    latest_by_station: dict[str, dict] = {}
    for r in recs:  # rows arrive ts-descending from the DB
        sid = str(r.get("station_id"))
        if sid not in latest_by_station:
            r["evidence"] = _loads(r.pop("evidence_json", None), [])
            latest_by_station[sid] = r
    return list(latest_by_station.values())


class WhatIfRequest(BaseModel):
    station_id: str
    action_key: str


@app.post("/api/whatif/simulate")
def post_whatif(req: WhatIfRequest) -> dict:
    with closing(_conn()) as conn:
        met = db.load_latest_metrics(conn)
    if met.empty:
        raise HTTPException(400, "no twin state available - generate data first")
    states = []
    for _, r in met.iterrows():
        def g(key, default):
            try:
                v = float(r.get(key, default))
            except (TypeError, ValueError):
                return default
            return v if pd.notna(v) else default
        states.append({
            "station_id": str(r["station_id"]),
            "avg_cycle_time": g("avg_cycle_time", 60.0),
            "sensor_coverage": g("sensor_coverage", 0.5),
            "health_score": g("health_score", 70.0),
            "bottleneck_prob": g("bottleneck_prob", 0.1),
        })
    out = simulate_action(states, req.station_id, req.action_key)
    if out is None:
        raise HTTPException(400, f"invalid station/action combination "
                                 f"({req.station_id}, {req.action_key})")
    # Fire-and-forget audit log - a persistence failure must never block the
    # user-visible result (same contract as the previous Streamlit UI).
    logged = True
    note = ""
    try:
        with closing(_conn()) as conn:
            db.insert_simulation_run(conn, {
                "run_id": str(uuid.uuid4()),
                "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "station_id": req.station_id,
                "action": req.action_key,
                "before": out["before"], "after": out["after"],
                "projected_improvement_pct": out["projected_improvement_pct"],
                "note": "SIMULATION ONLY"})
    except Exception as e:  # noqa: BLE001 - deliberate swallow, see above
        logged = False
        note = str(e)
    out["logged"] = logged
    if note:
        out["log_note"] = note
    return out


@app.get("/api/whatif/actions")
def get_actions() -> dict:
    return {"actions": ACTIONS}


class PlcWriteRequest(BaseModel):
    command: str = "test"


@app.post("/api/plc/write")
def post_plc_write(req: PlcWriteRequest) -> dict:
    """Live safety proof: calls the real, unmodified PLCAdapter.write(),
    which unconditionally raises RuntimeError. Nothing else in this service
    ever attempts a plant write."""
    adapter = PLCAdapter()
    try:
        adapter.write(req.command)
    except RuntimeError as e:
        return {"attempted": True, "raised": "RuntimeError", "detail": str(e)}
    # Unreachable while WRITE_ENABLED stays False; if it ever flips, fail loud.
    raise HTTPException(500, "PLC write unexpectedly returned - safety invariant broken")


@app.get("/api/scenarios")
def get_scenarios() -> list[dict]:
    return [_scenario_dict(s) for s in all_scenarios()]


@app.post("/api/scenarios/inject")
def post_scenario_inject(req: dict) -> dict:
    key = str(req.get("scenario_key", ""))
    scenarios = {s.key for s in all_scenarios()}
    if key not in scenarios:
        raise HTTPException(400, f"unknown scenario '{key}'")
    with _sim_lock:
        result = apply_scenario(scenario_key=key)
    if not result.get("ok"):
        raise HTTPException(500, str(result.get("reason", "injection failed")))
    result.pop("states", None)  # dataclass objects are not JSON-safe
    return result


@app.post("/api/scenarios/reset")
def post_scenario_reset() -> dict:
    with _sim_lock:
        result = reset_simulation()
    if not result.get("ok"):
        raise HTTPException(500, str(result.get("reason", "reset failed")))
    result.pop("states", None)
    return {"ok": True, "anchor": result.get("anchor"),
            "vehicles": result.get("vehicles"),
            "telemetry_rows": result.get("telemetry_rows"),
            "active_scenario": "normal"}


@app.get("/api/analytics/confidence-curve")
def get_confidence_curve() -> list[dict]:
    """The missing-data experiment curve, computed live from the twin's own
    compute_confidence formula (illustrative by construction)."""
    covs = [1.0, 0.7, 0.5, 0.3, 0.1]
    return [
        {
            "coverage": c,
            "confidence": compute_confidence(c, obs_n=40, agreement=0.8,
                                             history_buckets=48),
            "detection_proxy": 100.0,
        }
        for c in covs
    ]
