"""What-if / recommendation simulator.

OBSERVE -> INFER -> RECOMMEND -> SIMULATE. There is deliberately NO path to
CONTROL: PLCAdapter.write always raises.
"""
from __future__ import annotations

from datetime import datetime

import numpy as np

SIMULATION_ONLY = True


class PLCAdapter:
    """Integration seam that is intentionally crippled in this prototype."""

    READ_ENABLED = False
    WRITE_ENABLED = False

    def read(self, tag: str):
        raise RuntimeError("PLC reads disabled in prototype simulation")

    def write(self, command) -> None:
        raise RuntimeError("PLC writes disabled in prototype simulation")


def _station_capacity_vph(eff_ct_sec: float, availability: float) -> float:
    if eff_ct_sec <= 0:
        return 0.0
    return 3600.0 / eff_ct_sec * float(np.clip(availability, 0.3, 1.0))


def line_throughput_vph(station_eff_ct: dict[str, float],
                        availabilities: dict[str, float]) -> float:
    caps = [_station_capacity_vph(station_eff_ct[s], availabilities.get(s, 0.95))
            for s in station_eff_ct]
    return round(min(caps) if caps else 0.0, 2)


def simulate_action(states: list[dict], station_id: str, action_key: str
                    ) -> dict | None:
    """Re-run the twin projection after a *simulated* improvement.

    states: rows from TwinInference (dicts with health/ct/queue fields).
    Nothing outside this function is mutated; nothing is written to any PLC.
    """
    target = next((s for s in states if s["station_id"] == station_id), None)
    if target is None:
        return None

    actions = {
        "reduce_buffer_release": dict(ct_impr=0.10, queue_impr=0.35,
                                      label="Reduce conveyor buffer release threshold"),
        "increase_inspection": dict(ct_impr=0.02, defect_impr=0.45,
                                    label="Increase inspection sampling"),
        "schedule_maintenance": dict(ct_impr=0.16, anomaly_impr=0.40,
                                     label="Schedule preventive maintenance"),
        "recalibrate_sensors": dict(coverage_impr=0.55,
                                    label="Recalibrate / reconnect sensors"),
        "rebalance_work_content": dict(ct_impr=0.12,
                                       label="Rebalance work content across stations"),
    }
    act = actions.get(action_key)
    if act is None:
        return None

    eff_ct = {s["station_id"]: max(
        s["avg_cycle_time"] or 60.0,
        (s["avg_cycle_time"] or 60.0)) for s in states}
    avail = {s["station_id"]: float(np.clip(s["sensor_coverage"] + 0.55, 0.5, 1.0))
             for s in states}

    before_vph = line_throughput_vph(eff_ct, avail)

    t = target["station_id"]
    ct_new = eff_ct[t] * (1 - act.get("ct_impr", 0.0))
    eff_ct[t] = ct_new
    avail[t] = min(avail[t] + 0.05, 1.0)

    after_vph = line_throughput_vph(eff_ct, avail)

    projected_health = min(100.0, target["health_score"] + (
        18 * act.get("ct_impr", 0) * 4 + 12 * act.get("anomaly_impr", 0)))
    projected_bottleneck = max(0.0, target["bottleneck_prob"]
                               - 0.30 * act.get("ct_impr", 0) * 2
                               - 0.15 * act.get("queue_impr", 0))
    projected_coverage = min(1.0, target["sensor_coverage"]
                             + act.get("coverage_impr", 0.0))

    improvement_pct = ((after_vph - before_vph) / before_vph * 100.0
                       if before_vph > 0 else 0.0)
    return {
        "before": {
            "throughput_vph": before_vph,
            "station_cycle_time": round(target["avg_cycle_time"], 1),
            "health": target["health_score"],
            "bottleneck_prob": target["bottleneck_prob"],
        },
        "after": {
            "throughput_vph": after_vph,
            "station_cycle_time": round(ct_new, 1),
            "projected_health": round(projected_health, 1),
            "projected_bottleneck_prob": round(float(projected_bottleneck), 3),
            "projected_sensor_coverage": round(projected_coverage, 3),
        },
        "projected_improvement_pct": round(improvement_pct, 2),
        "action_label": act["label"],
        "simulation_only": SIMULATION_ONLY,
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


ACTIONS = {
    "reduce_buffer_release": "Reduce conveyor buffer release threshold",
    "increase_inspection": "Increase inspection sampling",
    "schedule_maintenance": "Schedule preventive maintenance",
    "recalibrate_sensors": "Recalibrate / reconnect sensors",
    "rebalance_work_content": "Rebalance work content across stations",
}
