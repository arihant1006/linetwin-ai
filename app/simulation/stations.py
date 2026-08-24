"""Per-station runtime behaviour: service times, states, maintenance windows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.config.plant_config import STATION_TYPE_MODEL_FACTOR

STARVE_THRESHOLD_SEC = 110.0
BLOCK_THRESHOLD_SEC = 60.0


@dataclass
class MaintenanceWindow:
    station_id: str
    start: datetime
    end: datetime


@dataclass
class StationState:
    free_at: datetime = field(default_factory=lambda: datetime(2000, 1, 1))


def sample_maintenance_windows(specs: pd.DataFrame, start: datetime, end: datetime,
                               rng: np.random.Generator,
                               per_day: int = 2) -> list[MaintenanceWindow]:
    windows: list[MaintenanceWindow] = []
    day = pd.Timestamp(start).floor("D")
    stop = pd.Timestamp(end)
    ids = list(specs.index)
    while day < stop:
        for _ in range(per_day):
            sid = ids[int(rng.integers(len(ids)))]
            hour = int(rng.choice([11, 12, 16, 17]))
            minute = int(rng.integers(0, 60))
            dur = float(rng.uniform(12, 28))
            st = (day + timedelta(hours=hour, minutes=minute)).to_pydatetime()
            windows.append(MaintenanceWindow(sid, st, st + timedelta(minutes=dur)))
        day += timedelta(days=1)
    return windows


class StationRuntime:
    def __init__(self, specs: pd.DataFrame):
        self.specs = specs
        self._type = specs["station_type"].to_dict()
        self._ct = specs["cycle_time_target"].to_dict()
        self._std = specs["cycle_time_std"].to_dict()

    def service_time(self, sid: str, model: str, ct_mult: float = 1.0,
                     rng: np.random.Generator | None = None) -> float:
        rng = rng or np.random.default_rng()
        base = self._ct[sid]
        std = self._std[sid]
        f_type = STATION_TYPE_MODEL_FACTOR.get(self._type[sid], {}).get(model, 1.0)
        val = rng.normal(base * f_type * ct_mult, std)
        return float(max(val, base * f_type * 0.55))

    @staticmethod
    def classify(queue_wait_sec: float, idle_before_sec: float, will_block_next: bool,
                 maintenance: bool, changeover: bool) -> str:
        """STARVED = station sat idle waiting for parts (upstream shortfall).
        Long queue_wait alone is congestion, not starvation."""
        if maintenance:
            return "MAINTENANCE"
        if changeover:
            return "CHANGEOVER"
        if queue_wait_sec > STARVE_THRESHOLD_SEC and idle_before_sec \
                > STARVE_THRESHOLD_SEC * 0.5:
            return "STARVED"
        if will_block_next:
            return "BLOCKED"
        return "RUNNING"
