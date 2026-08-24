"""Safety envelope: no PLC control path, simulation-only advice, no network code."""
from __future__ import annotations

import pytest

from app.analytics.inference import StationState
from app.analytics.recommendations import recommend_all
from app.analytics.whatif import PLCAdapter


def test_plc_write_raises():
    adapter = PLCAdapter()
    with pytest.raises(RuntimeError):
        adapter.write({"x": 1})
    with pytest.raises(RuntimeError):
        adapter.read("Cell7.TorqueActual")


def _degraded_state() -> StationState:
    """Manually constructed state that trips multiple recommendation rules."""
    return StationState(
        station_id="B07",
        bucket_ts="2026-08-20 12:00:00",
        health_score=50.0,
        anomaly_score=60.0,
        bottleneck_score=70.0,
        bottleneck_prob=0.66,
        confidence=80.0,
        status="Degraded",
        sensor_coverage=0.30,
        throughput_vph=18.0,
        cycle_time_deviation=20.0,
        queue_pressure=0.90,
        starvation_rate=0.30,
        blocking_rate=0.20,
        defect_rate=0.10,
        is_root_cause_candidate=True,
        causes=["Cycle-time drift vs baseline"],
        explanation=[{"factor": "test", "detail": "constructed", "weight": 1.0}],
    )


def test_recommendations_simulation_only():
    recs = recommend_all([_degraded_state()], top_n=8)
    assert len(recs) >= 1, "degraded state should trigger at least one rule"
    for r in recs:
        assert r.get("simulation_only") is True, \
            f"recommendation not flagged simulation-only: {r}"
        assert isinstance(r.get("recommended_action"), str) \
            and r["recommended_action"].strip(), \
            f"empty recommended_action in {r}"


def test_no_network_imports():
    """Guard: no industrial-network or HTTP-client code may sneak into app/."""
    forbidden = ["modbus", "opcua", "asyncua", "snap7", "socket.connect",
                 "requests.post", "pymodbus"]
    app_dir = __import__("pathlib").Path(__file__).resolve().parents[1] / "app"
    hits = []
    for py in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in py.parts:
            continue
        text = py.read_text(encoding="utf-8", errors="replace").lower()
        for needle in forbidden:
            if needle in text:
                hits.append(f"{py.name}: contains '{needle}'")
    assert not hits, f"forbidden integration code found:\n" + "\n".join(hits)
