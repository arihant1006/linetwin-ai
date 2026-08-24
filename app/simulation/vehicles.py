"""Vehicle generation for mixed-model production."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from app.config.plant_config import (MODEL_MIX, SHIFT_END_HOUR, SHIFT_START_HOUR,
                                     VEHICLE_MODELS)


class VehicleGenerator:
    def __init__(self, seed: int = 42, start_counter: int = 0):
        self.seed = seed
        self.counter = start_counter

    def next_ids(self, n: int) -> list[str]:
        out = [f"VH-{self.counter + i + 1:06d}" for i in range(n)]
        self.counter += n
        return out

    def sample_models(self, n: int, rng: np.random.Generator,
                      model_mix: dict | None = None) -> np.ndarray:
        mix = model_mix or MODEL_MIX
        models = sorted(mix.keys())
        probs = np.array([mix[m] for m in models], dtype=float)
        probs = probs / probs.sum()
        return rng.choice(models, size=n, p=probs)

    @staticmethod
    def _in_production_hours(ts: pd.Timestamp) -> bool:
        return SHIFT_START_HOUR <= ts.hour < SHIFT_END_HOUR

    def entry_times(self, start: datetime, end: datetime, target_rate_vph: float,
                    rng: np.random.Generator) -> list[datetime]:
        times: list[datetime] = []
        cur = pd.Timestamp(start).floor("h")
        stop = pd.Timestamp(end)
        while cur < stop:
            if self._in_production_hours(cur):
                hour_frac = cur.hour + cur.minute / 60.0
                shift_pos = (cur.hour - SHIFT_START_HOUR) / max(
                    1, SHIFT_END_HOUR - SHIFT_START_HOUR)
                wave = 1.0 + 0.18 * np.sin(2 * np.pi * min(max(shift_pos, 0), 1))
                rate = target_rate_vph * wave
                n = rng.poisson(rate)
                minutes = rng.uniform(0, 60, size=n)
                day = cur.floor("D")
                for m in minutes:
                    t = day + timedelta(minutes=float(cur.hour * 60 + m))
                    if start <= t < end and self._in_production_hours(t):
                        times.append(t.to_pydatetime())
            cur += timedelta(hours=1)
        times.sort()
        return times
