#!/usr/bin/env python
"""Judge demo, end-to-end:

1. reset_simulation()            - fresh 7-day normal history
2. apply_scenario(b07_mechanical)- inject the B07 failure into the live window
3. rank bottlenecks, show alerts / defect chains / recommendations
4. print dashboard demo instructions + PASS/FAIL check that B07 ranks top-3
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pandas as pd  # noqa: E402

from app.data import database as db  # noqa: E402
from app.simulation.inject import apply_scenario, reset_simulation  # noqa: E402


def _hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _ranked_snapshot(conn) -> pd.DataFrame:
    """Latest twin-state snapshot ranked by bottleneck_prob.

    The engine scores exactly one bucket per inference run. When the anchor
    falls near a shift boundary that final bucket can be a partially populated
    drain bucket (only tail-of-line stations), so we prefer the newest scored
    bucket holding >= 90% of the line; if none qualifies we recompute states
    deterministically over the newest equally-complete telemetry bucket using
    the same documented pipeline (compute_features + TwinInference).
    """
    specs = db.load_stations(conn)
    n_stations = max(len(specs), 1)
    hist = db.load_metric_history(conn)
    if not hist.empty:
        scored = hist[hist["health_score"].notna()]
        if not scored.empty:
            sizes = scored.groupby("bucket_ts")["station_id"].nunique()
            good = sizes[sizes >= int(0.9 * n_stations)]
            if not good.empty:
                latest_ts = good.index.max()
                snap = scored[scored["bucket_ts"] == latest_ts]
                return snap.sort_values("bottleneck_prob", ascending=False)

    # Fallback: recompute the snapshot from stored telemetry.
    from app.analytics.features import compute_features
    from app.analytics.inference import TwinInference
    from app.simulation.plant import PlantModel

    tel = db.load_telemetry(conn)
    if tel.empty or specs.empty:
        return pd.DataFrame()
    plant = PlantModel(specs)
    feat, _ = compute_features(tel, specs, plant)
    counts = feat.groupby(level="bucket_ts").size()
    full = counts[counts >= int(0.9 * n_stations)]
    target_ts = (full if len(full) else counts).index.max()
    trunc = feat[feat.index.get_level_values("bucket_ts") <= target_ts]
    states = TwinInference(specs, plant).update(trunc)
    rows = [{
        "bucket_ts": s.bucket_ts, "station_id": s.station_id,
        "health_score": s.health_score, "bottleneck_prob": s.bottleneck_prob,
        "confidence": s.confidence, "sensor_coverage": s.sensor_coverage,
        "status": s.status} for s in states]
    return pd.DataFrame(rows).sort_values("bottleneck_prob", ascending=False)


def main() -> int:
    _hr("STEP 1/2 - reset_simulation(): fresh 7-day NORMAL production history")
    res = reset_simulation(rate_vph=46.0)
    if not res.get("ok"):
        print(f"FAILED: {res.get('reason', 'unknown error')}")
        return 1
    print(f"stations={res.get('stations')}  vehicles={res.get('vehicles')}  "
          f"telemetry_rows={res.get('telemetry_rows')}")

    _hr("STEP 2/2 - apply_scenario('b07_mechanical'): inject failure into live window")
    res2 = apply_scenario(scenario_key="b07_mechanical")
    if not res2.get("ok"):
        print(f"FAILED: {res2.get('reason', 'unknown error')}")
        return 1
    print(f"scenario applied: window_hours={res2.get('window_hours')}  "
          f"telemetry_rows_added={res2.get('telemetry_rows_added')}  "
          f"vehicles_added={res2.get('vehicles_added')}")

    conn = db.get_conn()
    try:
        ranked = _ranked_snapshot(conn)
        alerts = db.load_alerts(conn, active_only=True, limit=100)
        defects = db.load_defects(conn, limit=200)
        recs = db.load_recommendations(conn, limit=100)
        scenario = db.get_meta(conn, "active_scenario", "normal")
    finally:
        conn.close()

    root_cause_ids: set[str] = set()
    if not alerts.empty and "kind" in alerts.columns:
        root_cause_ids = set(alerts.loc[alerts["kind"] == "root_cause", "station_id"])

    _hr(f"TWIN STATE SNAPSHOT - ranked bottleneck table (scenario: {scenario})")
    if ranked.empty:
        print("(no scored metrics available)")
    else:
        print(f"{'rank':<5}{'station':<8}{'health':>7}{'bottleneck_p':>14}"
              f"{'confidence':>12}{'coverage':>10}  {'status':<10}root_cause")
        for i, r in enumerate(ranked.head(8).itertuples(), 1):
            flag = "YES" if r.station_id in root_cause_ids else "-"
            print(f"{i:<5}{r.station_id:<8}{r.health_score:>7.1f}"
                  f"{r.bottleneck_prob:>14.3f}{r.confidence:>12.1f}"
                  f"{r.sensor_coverage:>10.0%}  {r.status:<10}{flag}")

    _hr("ACTIVE ALERTS (severity / station / message)")
    if alerts.empty:
        print("(none - all stations within normal bands)")
    else:
        for a in alerts.itertuples():
            print(f"[{a.severity:<8}] {a.station_id}: {a.message}")

    _hr("DEFECT CHAINS (origin -> propagation path -> detected)")
    if defects.empty:
        print("(none detected in current window)")
    else:
        for d in defects.itertuples():
            try:
                import json as _json
                chain = " -> ".join(_json.loads(d.affected_stations_json)) \
                    if d.affected_stations_json else "(no path)"
            except Exception:
                chain = "(unparseable path)"
            det = f"{d.detected_station} @ {d.ts_detected}" if d.detected_station \
                else "escaped detection"
            print(f"{d.origin_station}: {chain}   [detected: {det}]")

    _hr("TOP RECOMMENDATIONS (issue / action / confidence) - simulation only")
    if recs.empty:
        print("(none)")
    else:
        for r in recs.head(5).itertuples():
            print(f"- [{r.station_id}] {r.issue}\n    action: {r.recommended_action}"
                  f"\n    confidence: {r.confidence:.0%} (simulation_only="
                  f"{bool(r.simulation_only)})")

    _hr("DEMO INSTRUCTIONS")
    print(
        "1. Launch the dashboard:\n"
        "       .venv/bin/python run.py\n"
        "   (or: .venv/bin/streamlit run app/dashboard.py)\n"
        "\n"
        "2. In the left sidebar:\n"
        "   - 'Simulation Scenario' selectbox: pick a failure scenario\n"
        "     (e.g. 'B07 Mechanical Degradation' or 'Multi-Causal Failure').\n"
        "   - Click the 'Inject Failure' button: the last production window is\n"
        "     re-simulated under that failure and the twin re-infers state.\n"
        "   - Watch the bottleneck ranking, station drill-down 'Why?' bullets,\n"
        "     defect-chain Sankey, alerts feed and recommendation cards react.\n"
        "   - Click 'Reset Simulation' to return to healthy production.\n"
        "   - Optional: 'Generate New Shift' extends the history with fresh data.\n"
        "\n"
        "3. CLI equivalents:\n"
        f"       .venv/bin/python {'scripts/demo_scenario.py'}      # this script\n"
        "       .venv/bin/python scripts/generate_data.py --days 7\n"
        "       .venv/bin/python scripts/reset_database.py --yes\n"
        "\n"
        "Note: every action is OBSERVE -> INFER -> RECOMMEND -> SIMULATE.\n"
        "There is no control path: PLC writes are hard-disabled (RuntimeError).")

    _hr("ASSERTION: B07 among top-3 stations by bottleneck_prob")
    if ranked.empty:
        print("FAIL: no ranked metrics to evaluate")
        return 0
    top3 = ranked.head(3)
    b07_row = ranked[ranked["station_id"] == "B07"]
    if "B07" in set(top3["station_id"]):
        prob = float(b07_row["bottleneck_prob"].iloc[0])
        rank_i = int((ranked["station_id"].reset_index(drop=True) == "B07").idxmax()) + 1
        print(f"PASS: B07 ranked #{rank_i} with bottleneck_prob={prob:.3f} "
              f"(top-3: {', '.join(f'{s.station_id}={s.bottleneck_prob:.3f}' for s in top3.itertuples())})")
    else:
        probs = ", ".join(f"{r.station_id}={r.bottleneck_prob:.3f}"
                          for r in top3.itertuples())
        b07_txt = (f"B07 bottleneck_prob={float(b07_row['bottleneck_prob'].iloc[0]):.3f}, "
                   f"rank=#{int((ranked['station_id'].reset_index(drop=True) == 'B07').idxmax()) + 1}"
                   if not b07_row.empty else "B07 absent from snapshot")
        print(f"FAIL: B07 not in top-3 by bottleneck_prob | top-3: {probs} | {b07_txt}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
