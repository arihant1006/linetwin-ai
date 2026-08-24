"""Defect propagation over the production-flow graph."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from app.simulation.plant import PlantModel

INSPECTION_TYPES = {"vision_inspection", "inspection"}


def propagate_defect(origin: str, t_origin: datetime, defect_type: str,
                     severity: float, plant: PlantModel, rng: np.random.Generator,
                     p_propagate: float = 0.55, decay: float = 0.88,
                     max_hops: int | None = None) -> dict:
    """Simulate a latent defect flowing downstream until detected or absorbed.

    Returns a record matching the `defects` table schema.
    """
    chain = [origin]
    detected_at = None
    ts_detected = None
    p = p_propagate * np.clip(severity + 0.35, 0.2, 1.0)
    current_ts = pd.Timestamp(t_origin)
    idx = plant.stations.index(origin)
    hops = plant.stations[idx + 1:] if max_hops is None else \
        plant.stations[idx + 1:idx + 1 + max_hops]
    for sid in hops:
        travel_min = float(rng.uniform(8, 25))
        current_ts += pd.Timedelta(minutes=travel_min)
        stype = str(plant.specs.loc[sid, "station_type"])
        if rng.random() < p:
            chain.append(sid)
            if stype in INSPECTION_TYPES and rng.random() < 0.75:
                detected_at = sid
                ts_detected = current_ts.strftime("%Y-%m-%d %H:%M:%S")
                break
            p *= decay
        else:
            if stype in INSPECTION_TYPES and rng.random() < 0.30:
                pass
    return {
        "defect_id": f"DF-{int(pd.Timestamp(t_origin).timestamp())}-{origin}",
        "ts_origin": pd.Timestamp(t_origin).strftime("%Y-%m-%d %H:%M:%S"),
        "origin_station": origin,
        "defect_type": defect_type or "unspecified",
        "severity": float(np.clip(severity, 0.05, 1.0)),
        "propagation_probability": round(float(np.clip(p_propagate, 0.05, 0.95)), 3),
        "affected_stations": chain,
        "detected_station": detected_at,
        "ts_detected": ts_detected,
        "scenario": "",
    }


def build_chains_from_telemetry(telemetry_window: pd.DataFrame, plant: PlantModel,
                                seed: int = 42, max_chains: int = 12) -> list[dict]:
    """Derive defect chains for vehicles flagged defective in the window."""
    if telemetry_window.empty or "defective_here" not in telemetry_window.columns:
        return []
    rng = np.random.default_rng(seed + 77)
    tel = telemetry_window.copy()
    tel["ts"] = pd.to_datetime(tel["ts"])
    flagged = tel[tel["defective_here"] == 1].sort_values("ts")
    origins = flagged.groupby("station_id").size().sort_values(ascending=False)
    chains: list[dict] = []
    for origin, count in origins.items():
        if len(chains) >= max_chains:
            break
        sub = flagged[flagged["station_id"] == origin]
        n = min(len(sub), max(1, int(np.ceil(count / 6))))
        sample = sub.sample(n=min(n, len(sub)), random_state=seed)
        severity = float(np.clip(count / max(len(tel) / 400, 1.0), 0.3, 1.0))
        for r in sample.itertuples():
            rec = propagate_defect(r.station_id, r.ts.to_pydatetime(),
                                   "fastening_torque_drift", severity, plant, rng)
            rec["scenario"] = "window"
            chains.append(rec)
    seen = set()
    unique = []
    for c in chains:
        key = (c["origin_station"], c["detected_station"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique[:max_chains]


def sankey_edges(chains: list[dict]) -> list[tuple[str, str, int]]:
    """Origin -> ... -> detection edges with counts for Plotly Sankey."""
    counts: dict[tuple[str, str], int] = {}
    for c in chains:
        path = list(c.get("affected_stations", []))
        det = c.get("detected_station")
        nodes = []
        for s in path:
            if s not in nodes:
                nodes.append(s)
        if det and det not in nodes:
            nodes.append(det)
        for a, b in zip(nodes, nodes[1:]):
            counts[(a, b)] = counts.get((a, b), 0) + 1
    return [(a, b, n) for (a, b), n in sorted(counts.items(), key=lambda kv: -kv[1])]
