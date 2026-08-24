"""Telemetry generation: sensor availability, outages, realistic distributions."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.simulation.failures import InjectionPlan, random_outage_windows

CLASS_SENSORS = {
    "rich": ["torque", "vibration", "temperature", "motor_current", "pressure"],
    "medium": ["temperature"],
    "sparse": [],
}
ALWAYS_SENSORS = ("cycle_time", "machine_state")
MANUAL_CLASS = {"medium", "sparse"}

TEL_OUTPUT_COLS = ["ts", "station_id", "vehicle_id", "vehicle_model", "cycle_time",
                   "torque", "vibration", "temperature", "motor_current", "pressure",
                   "machine_state", "manual_checklist", "sensor_available",
                   "data_quality", "wait_sec", "defective_here"]

TORQUE_STATION_TYPES = {"welding", "fastening", "torque", "assembly", "electrical"}


def plan_random_outages(specs: pd.DataFrame, start: datetime, end: datetime,
                        seed: int) -> list[tuple[str, str, datetime, datetime]]:
    rich_ids = specs.index[specs["telemetry_class"] == "rich"].tolist()
    return random_outage_windows(rich_ids, start, end,
                                 np.random.default_rng(seed + 31))


class TelemetryBuilder:
    def __init__(self, specs: pd.DataFrame, seed: int = 42,
                 outages: list[tuple[str, str, datetime, datetime]] | None = None):
        self.specs = specs
        self.seed = seed
        self._class = specs["telemetry_class"].to_dict()
        self._cov = specs["sensor_coverage"].to_dict()
        self._ttype = specs["station_type"].to_dict()
        self._torque = specs["torque_target"].to_dict()
        self._ttol = specs["torque_tol"].to_dict()
        self.outages = list(outages or [])

    def add_outages(self, windows) -> None:
        self.outages.extend(windows)

    def _in_outage(self, sid: str, sensor: str, ts: datetime) -> bool:
        return any(s == sid and sen == sensor and t0 <= ts < t1
                   for s, sen, t0, t1 in self.outages)

    def build(self, visits: pd.DataFrame,
              plan: InjectionPlan | None = None) -> pd.DataFrame:
        rng = np.random.default_rng(self.seed + 47)
        profiles = plan.profiles if plan else {}
        z: dict[str, float] = {}
        rows = []
        if visits.empty:
            return pd.DataFrame(columns=TEL_OUTPUT_COLS)
        for r in visits.itertuples():
            sid = r.station_id
            ts_dt = datetime.strptime(r.ts, "%Y-%m-%d %H:%M:%S")
            cls = self._class[sid]
            prof = profiles.get(sid)
            drop_p = prof.dropout_prob_at(ts_dt) if prof else 0.0
            ramp = prof.ramp(ts_dt) if prof else 0.0

            class_sensors = list(CLASS_SENSORS[cls])
            avail: dict[str, bool] = {}
            for sensor in class_sensors:
                p_cov = self._cov[sid]
                hard_out = self._in_outage(sid, sensor, ts_dt)
                present = (rng.random() < p_cov) and (rng.random() >= drop_p * 1.4) \
                    and not hard_out
                avail[sensor] = bool(present)
            avail["cycle_time"] = True
            avail["machine_state"] = True

            zs = z.get(sid, 0.0)
            zs = 0.90 * zs + np.sqrt(1 - 0.90 ** 2) * float(rng.normal())
            z[sid] = zs

            ct_val = float(r.cycle_time) + rng.normal(0, 0.4)
            vib_mult = 1.0 + ((prof.vib_mult - 1.0) * ramp if prof else 0.0)
            temp_add = prof.temp_add * ramp if prof else 0.0
            cur_mult = 1.0 + ((prof.current_mult - 1.0) * ramp if prof else 0.0)
            t_bias = prof.torque_bias * ramp if prof else 0.0

            def maybe(name: str, val: float) -> float:
                return round(val, 3) if avail.get(name) else np.nan

            torque_v = np.nan
            if self._ttype[sid] in TORQUE_STATION_TYPES and avail.get("torque"):
                target = self._torque[sid]
                delta_mul = {"Model-A": 1.0, "Model-B": 1.03,
                             "Model-C": 1.07, "Model-D": 1.05}.get(r.vehicle_model, 1.0)
                torque_v = round(float(rng.normal(
                    target * delta_mul * (1 + t_bias),
                    max(self._ttol[sid] / 3, 0.5))), 2)

            fail_p = 0.02
            if prof and prof.checklist_fail_add:
                fail_p += prof.checklist_fail_add * min(ramp * 1.5, 1.0)
            checklist = int(rng.random() >= fail_p) if cls in MANUAL_CLASS else None

            n_class = len(class_sensors)
            n_present = sum(1 for s in class_sensors if avail[s])
            expected = n_class + len(ALWAYS_SENSORS)
            got = n_present + len(ALWAYS_SENSORS)
            sensor_available = got / max(expected, 1)
            data_quality = float(np.clip(sensor_available * rng.uniform(0.82, 1.0),
                                         0.05, 1.0))

            rows.append({
                "ts": r.ts, "station_id": sid, "vehicle_id": r.vehicle_id,
                "vehicle_model": r.vehicle_model,
                "cycle_time": round(ct_val, 2),
                "torque": torque_v,
                "vibration": maybe("vibration", 2.0 * vib_mult + zs * 0.12
                                   + rng.normal(0, 0.3)),
                "temperature": maybe("temperature", 65.0 + temp_add + zs * 1.6
                                     + rng.normal(0, 5.0)),
                "motor_current": maybe("motor_current", 38.0 * cur_mult + zs * 0.9
                                       + rng.normal(0, 2.2)),
                "pressure": maybe("pressure", 6.2 + rng.normal(0, 0.25)),
                "machine_state": r.machine_state,
                "manual_checklist": checklist,
                "sensor_available": round(sensor_available, 3),
                "data_quality": round(data_quality, 3),
                "wait_sec": float(r.gap_sec),
                "defective_here": int(getattr(r, "defective_here", 0)),
            })
        tel = pd.DataFrame(rows, columns=TEL_OUTPUT_COLS)
        return tel.sort_values(["ts", "station_id"]).reset_index(drop=True)

    @staticmethod
    def effective_coverage(tel_station: pd.DataFrame, nominal: float) -> float:
        """Nominal coverage modulated by observed channel availability."""
        if tel_station.empty:
            return float(nominal)
        return round(float(np.clip(
            nominal * float(tel_station["sensor_available"].mean()), 0.02, 1.0)), 3)
