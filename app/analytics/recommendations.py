"""Rule-based recommendation engine (OBSERVE/INFER/RECOMMEND only - never CONTROL)."""
from __future__ import annotations

from datetime import datetime

from app.analytics.inference import StationState


def _ev(state: StationState) -> list[str]:
    ev = [f"health={state.health_score:.0f}", f"confidence={state.confidence:.0f}%",
          f"coverage={state.sensor_coverage:.0%}"]
    return ev


RULES: list[dict] = [
    dict(key="vibration", when=lambda s: s.anomaly_score > 45 and s.health_score < 65,
         issue="High vibration / telemetry anomaly",
         action="Inspect spindle, mounts and drive motor alignment",
         effect="Reduce mechanical wear; recover cycle time",
         conf=lambda s: min(0.55 + s.anomaly_score / 250.0, 0.92)),
    dict(key="cycle_time", when=lambda s: s.cycle_time_deviation > 12,
         issue="Cycle-time drift above baseline",
         action="Inspect workstation process and fixture condition",
         effect="Recover target cycle time; relieve upstream queue",
         conf=lambda s: min(0.50 + abs(s.cycle_time_deviation) / 100.0, 0.90)),
    dict(key="queue", when=lambda s: s.queue_pressure > 0.75,
         issue="Upstream queue build-up",
         action=f"Investigate upstream stations for flow restriction",
         effect="Dissolve queue before it starves downstream",
         conf=lambda s: 0.72),
    dict(key="starve", when=lambda s: s.starvation_rate > 0.18
         and not s.is_root_cause_candidate,
         issue="Downstream starvation events",
         action="Investigate upstream station feeding this segment",
         effect="Restore steady part supply to downstream area",
         conf=lambda s: 0.68),
    dict(key="manual", when=lambda s: (s.defect_rate > 0.05),
         issue="Elevated defect creation at station",
         action="Increase inspection sampling and audit work instructions",
         effect="Contain defects before they propagate downstream",
         conf=lambda s: min(0.5 + s.defect_rate * 2.0, 0.9)),
    dict(key="sensor", when=lambda s: s.sensor_coverage < 0.45 and s.health_score < 60,
         issue="Sensor coverage degraded while health declining",
         action="Verify sensor connectivity and recalibrate telemetry channels",
         effect="Restore observability; raise inference confidence",
         conf=lambda s: 0.66),
]


def recommend(state: StationState, ts: datetime | None = None) -> list[dict]:
    out = []
    now = (ts or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    for rule in RULES:
        try:
            hit = rule["when"](state)
        except Exception:
            hit = False
        if not hit:
            continue
        evidence = _ev(state)
        if state.is_root_cause_candidate:
            evidence.append("ranked top root-cause candidate")
        evidence += state.causes[:2]
        out.append({
            "rec_id": f"RC-{now.replace(' ', 'T').replace(':', '')}-{state.station_id}-{rule['key']}",
            "ts": now,
            "station_id": state.station_id,
            "issue": rule["issue"],
            "evidence": evidence,
            "recommended_action": rule["action"],
            "expected_effect": rule["effect"],
            "confidence": round(float(rule["conf"](state)), 2),
            "simulation_only": True,
        })
    return out


def recommend_all(states: list[StationState], top_n: int = 8) -> list[dict]:
    recs: list[dict] = []
    for s in sorted(states, key=lambda x: (-x.bottleneck_prob, x.health_score)):
        recs.extend(recommend(s))
        if len(recs) >= top_n:
            break
    for r in recs:
        r["simulation_only"] = True
    return recs[:top_n]
