"""Failure injection profiles and scenario-driven degradation."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from app.config.plant_config import ScenarioSpec


@dataclass
class DegradeProfile:
    station_id: str
    t_start: datetime
    t_end: datetime
    ramp_hours: float = 3.0
    ct_mult: float = 1.0
    vib_mult: float = 1.0
    temp_add: float = 0.0
    current_mult: float = 1.0
    torque_bias: float = 0.0
    sensor_dropout_sensors: tuple[str, ...] = ()
    sensor_dropout_p: float = 0.0
    checklist_fail_add: float = 0.0
    starve_gap_add: float = 0.0
    defect_rate_p: float = 0.0
    defect_type: str = ""
    note: str = ""

    def ramp(self, ts: datetime) -> float:
        if ts < self.t_start or ts >= self.t_end:
            return 0.0
        h = (ts - self.t_start).total_seconds() / 3600.0
        return float(min(1.0, h / max(self.ramp_hours, 1e-6)))

    def active(self, ts: datetime) -> bool:
        return self.t_start <= ts < self.t_end

    def ct_multiplier_at(self, ts: datetime) -> float:
        return 1.0 + (self.ct_mult - 1.0) * self.ramp(ts)

    def dropout_prob_at(self, ts: datetime) -> float:
        return self.sensor_dropout_p * self.ramp(ts)


@dataclass
class InjectionPlan:
    scenario: ScenarioSpec
    window_start: datetime
    window_end: datetime
    profiles: dict[str, DegradeProfile] = field(default_factory=dict)
    model_mix_override: dict | None = None
    outage_windows: list[tuple[str, str, datetime, datetime]] = field(default_factory=list)


class FailureInjector:
    def __init__(self, seed: int = 42):
        self.seed = seed

    def build_plan(self, scenario: ScenarioSpec, anchor_end: datetime) -> InjectionPlan:
        win_h = scenario.window_hours
        w_start = anchor_end - timedelta(hours=win_h)
        plan = InjectionPlan(scenario=scenario, window_start=w_start,
                             window_end=anchor_end,
                             model_mix_override=scenario.params.get("model_mix"))
        rng = np.random.default_rng((self.seed + sum(map(ord, scenario.key)) * 17) % 2**31)
        p = scenario.params

        if scenario.key in ("b07_mechanical", "multi_causal"):
            onset = w_start + timedelta(hours=float(rng.uniform(1.2, 2.2)))
            prof = DegradeProfile(
                station_id="B07", t_start=onset, t_end=anchor_end,
                ramp_hours=p.get("queue_ramp_hours", 3.0),
                ct_mult=p["ct_mult"], vib_mult=p["vib_mult"], temp_add=p["temp_add"],
                current_mult=p["current_mult"], torque_bias=p["torque_bias"],
                sensor_dropout_sensors=tuple(p.get("sensor_dropout_sensors", ())),
                sensor_dropout_p=p.get("sensor_dropout_p", 0.0),
                checklist_fail_add=p.get("checklist_fail_p", 0.0),
                defect_rate_p=p.get("defect_rate_p", 0.0),
                defect_type="fastening_torque_drift",
                note="mechanical degradation")
            plan.profiles["B07"] = prof
            for s in prof.sensor_dropout_sensors:
                plan.outage_windows.append(("B07", s, onset, anchor_end))

        if scenario.key in ("p04_sensor_failure", "multi_causal"):
            sid = "P04"
            onset = w_start + timedelta(hours=float(rng.uniform(1.5, 2.5)))
            drop_sensors = (("torque", "vibration", "temperature",
                             "motor_current", "pressure")
                            if scenario.key == "p04_sensor_failure" else ("temperature",))
            prof = DegradeProfile(
                station_id=sid, t_start=onset, t_end=anchor_end,
                ramp_hours=1.0, ct_mult=p.get("ct_mult", 1.05),
                sensor_dropout_sensors=drop_sensors,
                sensor_dropout_p=(p.get("sensor_dropout_p", 0.9)
                                  if scenario.key == "p04_sensor_failure"
                                  else p.get("secondary_sensor_dropout_p", 0.9)),
                checklist_fail_add=p.get("checklist_fail_p", 0.03),
                defect_rate_p=p.get("defect_rate_p", 0.05) if scenario.key == "p04_sensor_failure" else 0.0,
                defect_type="paint_coverage_fault" if scenario.key == "p04_sensor_failure" else "",
                note="telemetry outage, production continues")
            plan.profiles[sid] = prof
            for s in prof.sensor_dropout_sensors:
                plan.outage_windows.append((sid, s, onset, anchor_end))

        if scenario.key == "f12_quality_defect":
            onset = w_start + timedelta(hours=2.0)
            plan.profiles["B07"] = DegradeProfile(
                station_id="B07", t_start=onset, t_end=anchor_end,
                ramp_hours=1.5, ct_mult=1.04,
                defect_rate_p=p.get("defect_rate_p", 0.28),
                defect_type="fastening_torque_drift",
                note="latent quality defect origin")

        if scenario.key == "material_shortage":
            onset = w_start + timedelta(hours=1.5)
            plan.profiles["P05"] = DegradeProfile(
                station_id="P05", t_start=onset, t_end=anchor_end,
                ramp_hours=1.0, starve_gap_add=p.get("starve_gap_add", 210.0),
                checklist_fail_add=p.get("checklist_fail_p", 0.04),
                note="material starvation at cure area feed")
        return plan


def random_outage_windows(rich_ids: list[str], start: datetime, end: datetime,
                          rng: np.random.Generator
                          ) -> list[tuple[str, str, datetime, datetime]]:
    out = []
    n_days = max(1, int((end - start).total_seconds() // 86400))
    for sid in rich_ids:
        for _ in range(n_days):
            if rng.random() < 0.35:
                base = start + timedelta(days=int(rng.integers(0, n_days)),
                                         hours=int(rng.integers(6, 20)),
                                         minutes=int(rng.integers(0, 60)))
                dur = timedelta(minutes=int(rng.uniform(25, 70)))
                out.append((sid, str(rng.choice(["torque", "vibration", "motor_current"])),
                            base, base + dur))
    return out
