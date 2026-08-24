"""Scenario injection semantics and normal-vs-failure twin comparison."""
from __future__ import annotations

import math
import os
from datetime import datetime

from app.data import database as db
from app.simulation.failures import FailureInjector
from app.simulation.scenarios import get_scenario


def _latest_metrics_at(path: str):
    """Fresh connection against the given db file ($DIGITALTWIN_DB switched)."""
    os.environ["DIGITALTWIN_DB"] = str(path)
    conn = db.get_conn()
    try:
        return db.load_latest_metrics(conn)
    finally:
        conn.close()


def test_failure_increases_bottleneck(tiny_db, tiny_db_failure, station_scores):
    def b07_pair_from_db():
        normal_met = _latest_metrics_at(tiny_db)
        failure_met = _latest_metrics_at(tiny_db_failure)

        def row_for(met, sid):
            sub = met[met["station_id"] == sid]
            return None if sub.empty else sub.iloc[0]

        n_row, f_row = row_for(normal_met, "B07"), row_for(failure_met, "B07")
        if n_row is None or f_row is None:
            return None
        vals = [float(n_row["bottleneck_prob"]), float(f_row["bottleneck_prob"]),
                float(n_row["health_score"]), float(f_row["health_score"])]
        if any(math.isnan(v) for v in vals):
            return None  # stored snapshot predates scoring for one of the dbs
        return (vals[0], vals[2]), (vals[1], vals[3])

    pair = b07_pair_from_db()
    if pair is None:
        # Stored snapshot partial -> deterministic engine recomputation fallback.
        sn = station_scores(tiny_db)["B07"]
        sf = station_scores(tiny_db_failure)["B07"]
        pair = ((sn["bprob"], sn["health"]), (sf["bprob"], sf["health"]))

    (n_prob, n_health), (f_prob, f_health) = pair
    assert f_prob > n_prob, (
        f"B07 bottleneck_prob should rise under failure "
        f"(normal={n_prob:.3f}, failure={f_prob:.3f})")
    assert f_health < n_health, (
        f"B07 health should drop under failure "
        f"(normal={n_health:.1f}, failure={f_health:.1f})")


def test_multi_causal_plan():
    anchor = datetime(2026, 8, 20, 20, 0, 0)
    plan = FailureInjector(seed=42).build_plan(get_scenario("multi_causal"), anchor)
    assert "B07" in plan.profiles, "multi_causal must degrade B07"
    assert "P04" in plan.profiles, "multi_causal must hit P04 sensors too"
    assert plan.model_mix_override is not None, \
        "multi_causal must carry a model-mix override"


def test_material_shortage_starves():
    anchor = datetime(2026, 8, 20, 20, 0, 0)
    plan = FailureInjector(seed=42).build_plan(get_scenario("material_shortage"),
                                               anchor)
    profile = plan.profiles.get("P05")
    assert profile is not None, "material_shortage must target P05"
    assert profile.starve_gap_add > 0, \
        f"P05 starve_gap_add must be positive, got {profile.starve_gap_add}"
