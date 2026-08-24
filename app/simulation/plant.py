"""Production-flow graph over the 40-station line."""
from __future__ import annotations

import pandas as pd

from app.config.plant_config import AREA_PREFIX, build_station_specs


class PlantModel:
    def __init__(self, specs: pd.DataFrame | None = None):
        self.specs = (specs if specs is not None else build_station_specs()).copy()
        self.specs = self.specs.sort_values("sequence")
        self.stations: list[str] = list(self.specs.index)
        self._pos = {sid: i for i, sid in enumerate(self.stations)}

    def __contains__(self, sid: str) -> bool:
        return sid in self._pos

    def next_station(self, sid: str) -> str | None:
        i = self._pos.get(sid)
        return self.stations[i + 1] if i is not None and i + 1 < len(self.stations) else None

    def prev_station(self, sid: str) -> str | None:
        i = self._pos.get(sid)
        return self.stations[i - 1] if i is not None and i > 0 else None

    def downstream_chain(self, sid: str, k: int | None = None) -> list[str]:
        i = self._pos.get(sid, -1)
        out = self.stations[i + 1:]
        return out if k is None else out[:k]

    def upstream_chain(self, sid: str, k: int | None = None) -> list[str]:
        i = self._pos.get(sid, 0)
        out = list(reversed(self.stations[:i]))
        return out if k is None else out[:k]

    def neighbors(self, sid: str, k: int = 2) -> list[str]:
        up = self.upstream_chain(sid, k)
        down = self.downstream_chain(sid, k)
        return up + down

    def area_of(self, sid: str) -> str:
        return str(self.specs.loc[sid, "area"]) if sid in self.specs.index else ""

    def area_boundary_crossings(self) -> dict[str, tuple[str, str]]:
        out = {}
        for a, b in zip(self.stations, self.stations[1:]):
            if self.area_of(a) != self.area_of(b):
                out[a] = (self.area_of(a), b)
        return out

    def station_ids_by_area(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for sid in self.stations:
            out.setdefault(self.area_of(sid), []).append(sid)
        return out

    @staticmethod
    def prefix_of_area(area: str) -> str:
        return AREA_PREFIX.get(area, "")
