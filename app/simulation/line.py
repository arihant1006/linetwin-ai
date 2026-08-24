"""Discrete-event line simulation: vehicle traversal producing raw station visits."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.simulation.failures import DegradeProfile, InjectionPlan
from app.simulation.stations import (BLOCK_THRESHOLD_SEC, StationRuntime,
                                     MaintenanceWindow, sample_maintenance_windows)
from app.simulation.vehicles import VehicleGenerator

VISIT_COLS = ["vehicle_id", "vehicle_model", "station_id", "ts", "cycle_time",
              "gap_sec", "machine_state", "blocked", "defective_here", "maintenance"]


@dataclass
class LineRunResult:
    visits: pd.DataFrame
    vehicles: pd.DataFrame


class LineSimulator:
    def __init__(self, specs: pd.DataFrame, seed: int = 42):
        self.specs = specs
        self.stations = list(specs.sort_values("sequence").index)
        self.runtime = StationRuntime(specs)
        self.seed = seed

    def run(self, start: datetime, end: datetime, target_rate_vph: float = 21.0,
            plan: InjectionPlan | None = None, vehicle_offset: int = 0) -> LineRunResult:
        rng = np.random.default_rng(self.seed)
        vg = VehicleGenerator(seed=self.seed + 5, start_counter=vehicle_offset)
        mix_override = plan.model_mix_override if plan else None
        entries = vg.entry_times(start, end, target_rate_vph, rng)
        models = vg.sample_models(len(entries), np.random.default_rng(self.seed + 11),
                                  mix_override)
        v_ids = vg.next_ids(len(entries))
        maint = sample_maintenance_windows(self.specs, start, end,
                                           np.random.default_rng(self.seed + 23))
        free = {sid: None for sid in self.stations}
        prev_arrival = {sid: None for sid in self.stations}
        rows: list[dict] = []
        veh_rows: list[dict] = []
        profiles: dict[str, DegradeProfile] = plan.profiles if plan else {}

        for k, entry in enumerate(entries):
            vid, model = v_ids[k], str(models[k])
            ready = entry
            defective_from = None
            flags: list[str] = []
            last_sid = self.stations[-1]
            for sid in self.stations:
                ts_now = ready
                prof = profiles.get(sid)
                ct_mult = prof.ct_multiplier_at(ts_now) if prof else 1.0
                f_free = free[sid]
                arrival = ready if f_free is None else max(ready, f_free)
                idle_before = 0.0 if f_free is None else max(
                    (arrival - f_free).total_seconds(), 0.0)
                if prev_arrival[sid] is not None and arrival < prev_arrival[sid]:
                    arrival = prev_arrival[sid]
                prev_arrival[sid] = arrival
                gap = (arrival - ready).total_seconds()
                in_maint = any(m.station_id == sid and m.start <= arrival < m.end
                               for m in maint)
                service = self.runtime.service_time(sid, model, ct_mult, rng)
                changeover = (arrival.hour in (6, 14)) and arrival.minute < 8 \
                    and rng.random() < 0.12
                starve_extra = 0.0
                if prof and prof.starve_gap_add and prof.active(arrival):
                    r = prof.ramp(arrival)
                    starve_extra = float(rng.uniform(0.55, 1.0)) * prof.starve_gap_add * r
                    arrival = arrival + timedelta(seconds=starve_extra)
                    gap += starve_extra
                nxt = self.stations[self.stations.index(sid) + 1] \
                    if sid != self.stations[-1] else None
                will_block = False
                if nxt is not None:
                    nf = free[nxt]
                    if nf is not None and nf > arrival + timedelta(
                            seconds=service + BLOCK_THRESHOLD_SEC):
                        will_block = True
                state = StationRuntime.classify(gap, idle_before, will_block,
                                                in_maint, changeover)
                defect_here = False
                if prof and prof.defect_rate_p and prof.active(arrival):
                    r = prof.ramp(arrival)
                    p_def = prof.defect_rate_p * min(r * 2.0, 1.0)
                    if rng.random() < p_def:
                        defect_here = True
                        if defective_from is None:
                            defective_from = sid
                        flags.append(sid)
                ts_done = arrival + timedelta(seconds=service)
                free[sid] = ts_done
                rows.append({
                    "vehicle_id": vid, "vehicle_model": model, "station_id": sid,
                    "ts": arrival.strftime("%Y-%m-%d %H:%M:%S"),
                    "cycle_time": round(service, 2),
                    "gap_sec": round(max(gap, 0.0), 1),
                    "machine_state": state,
                    "blocked": int(will_block),
                    "defective_here": int(defect_here),
                    "maintenance": int(in_maint),
                })
                ready = ts_done
                last_sid = sid
            exit_ts = ready
            status = "DEFECT" if defective_from else (
                "SUSPECT" if flags else "OK")
            veh_rows.append({"vehicle_id": vid, "model": model,
                             "entry_ts": entry.strftime("%Y-%m-%d %H:%M:%S"),
                             "exit_ts": exit_ts.strftime("%Y-%m-%d %H:%M:%S"),
                             "current_station": last_sid,
                             "quality_status": status,
                             "defect_flags": __import__("json").dumps(sorted(set(flags)))})
        return LineRunResult(visits=pd.DataFrame(rows, columns=VISIT_COLS),
                             vehicles=pd.DataFrame(veh_rows))
