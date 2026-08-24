"""Inference output contracts: score bounds, determinism, explainability."""
from __future__ import annotations

import pandas as pd
import pytest

from app.analytics.features import compute_features
from app.analytics.inference import TwinInference


@pytest.fixture(scope="module")
def latest_metrics(tiny_db, open_db):
    conn = open_db(tiny_db)
    try:
        from app.data import database as db
        return db.load_latest_metrics(conn)
    finally:
        conn.close()


def test_health_bounds(station_scores, tiny_db):
    scores = station_scores(tiny_db)
    assert len(scores) >= 30, f"expected most stations scored, got {len(scores)}"
    for sid, s in scores.items():
        assert 0 <= s["health"] <= 100, f"{sid} health out of bounds: {s['health']}"
        assert 0 <= s["conf"] <= 100, f"{sid} confidence out of bounds: {s['conf']}"


def test_bottleneck_probability_bounds(latest_metrics):
    met = latest_metrics
    assert not met.empty
    bp = pd.to_numeric(met["bottleneck_prob"], errors="coerce").dropna()
    assert len(bp) > 0, "no bottleneck_prob values persisted"
    assert ((bp >= 0) & (bp <= 1)).all(), \
        f"bottleneck_prob outside [0,1]: {bp[(bp < 0) | (bp > 1)].tolist()}"


def _engine_states(specs, plant, tel: pd.DataFrame):
    feat, _ = compute_features(tel, specs, plant)
    engine = TwinInference(specs, plant)
    return engine.update(feat)


def test_scores_deterministic(tiny_db, specs, plant, load_telemetry_for):
    tel_a = load_telemetry_for(tiny_db)
    tel_b = load_telemetry_for(tiny_db)  # loaded twice on purpose

    states_a = _engine_states(specs, plant, tel_a)
    states_b = _engine_states(specs, plant, tel_b)

    assert len(states_a) == len(states_b) > 0
    first5_a = [(s.station_id, s.health_score, s.bottleneck_prob) for s in states_a[:5]]
    first5_b = [(s.station_id, s.health_score, s.bottleneck_prob) for s in states_b[:5]]
    assert first5_a == first5_b, \
        f"non-deterministic inference:\n  {first5_a}\n  {first5_b}"


def test_explanation_present(tiny_db, specs, plant, load_telemetry_for):
    tel = load_telemetry_for(tiny_db)
    states = _engine_states(specs, plant, tel)
    assert states, "inference produced no states"
    for s in states:
        assert isinstance(s.explanation, list) and len(s.explanation) > 0, \
            f"{s.station_id} missing explanation factors"
        assert isinstance(s.causes, list) and len(s.causes) > 0, \
            f"{s.station_id} missing causes"
