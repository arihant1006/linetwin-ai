"""Missing-data semantics: NaN channels, outage gaps, sparse-station inference."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from app.analytics.health import compute_confidence
from app.config.plant_config import TELEMETRY_CLASS_MAP
from app.simulation.line import LineSimulator
from app.simulation.sensors import TelemetryBuilder
from app.simulation.scenarios import build_plan, get_scenario


def test_telemetry_contains_nans(tiny_db, load_telemetry_for):
    tel = load_telemetry_for(tiny_db)
    assert not tel.empty
    for col in ("torque", "vibration", "temperature"):
        assert tel[col].isna().any(), f"expected missing values in '{col}' column"


def test_outage_window_creates_gap(specs):
    anchor = datetime(2026, 8, 20, 20, 0, 0)
    plan = build_plan(get_scenario("p04_sensor_failure"), anchor, seed=42)
    profile = plan.profiles["P04"]
    onset = pd.Timestamp(profile.t_start)

    sim = LineSimulator(specs, seed=42)
    run = sim.run(anchor - timedelta(hours=8), anchor, target_rate_vph=20)

    tb = TelemetryBuilder(specs, seed=42, outages=[])
    tb.add_outages(plan.outage_windows)
    tel = tb.build(run.visits, plan)

    p04 = tel[tel["station_id"] == "P04"].copy()
    p04["ts_dt"] = pd.to_datetime(p04["ts"])
    pre = p04[p04["ts_dt"] < onset]
    post = p04[p04["ts_dt"] >= onset]
    assert len(pre) > 0 and len(post) > 0, "need visits on both sides of the onset"

    pre_mean = float(pre["sensor_available"].mean())
    post_mean = float(post["sensor_available"].mean())
    assert post_mean < pre_mean + 1e-9, \
        f"P04 availability must drop after outage onset (pre={pre_mean:.3f}, post={post_mean:.3f})"
    assert post_mean < 0.5, \
        f"P04 post-onset availability should be mostly down (got {post_mean:.3f})"


def test_sparse_stations_get_health_estimates(tiny_db, station_scores):
    scores = station_scores(tiny_db)
    sparse_ids = TELEMETRY_CLASS_MAP["sparse"]
    missing = [sid for sid in sparse_ids if sid not in scores]
    assert not missing, f"sparse stations missing from twin snapshot: {missing}"
    for sid in sparse_ids:
        s = scores[sid]
        assert s["health"] is not None, f"{sid} has no health estimate"
        assert s["conf"] >= 3, f"{sid} confidence {s['conf']} below floor of 3"


def test_confidence_lower_with_less_coverage():
    hi = compute_confidence(sensor_coverage=0.95, obs_n=40, agreement=0.8,
                            history_buckets=16)
    lo = compute_confidence(sensor_coverage=0.15, obs_n=40, agreement=0.8,
                            history_buckets=16)
    assert hi > lo, f"confidence must decrease with coverage ({hi} vs {lo})"
