"""Bottleneck scoring, probability and root-cause ranking."""
from __future__ import annotations

import numpy as np
import pandas as pd


def bottleneck_evidence(row: pd.Series) -> dict[str, float]:
    """Raw normalized evidence channels (0-1 each).

    downstream_starvation / upstream_blocking use *context* columns (mean
    starvation of the next 3 stations, mean queue pressure of the previous 2)
    so a constraining station is scored by its effect on flow, not only by its
    own local sensors.
    """
    ct_dev = max(float(row.get("ct_dev_ex_mix_pct", 0.0) or 0.0), 0.0)
    stv_own = float(row.get("starvation_freq", 0.0) or 0.0)
    stv_ctx = row.get("downstream_stv_mean")
    stv_ctx = float(stv_ctx) if stv_ctx is not None and not (
        isinstance(stv_ctx, float) and np.isnan(stv_ctx)) else stv_own
    blk_own = float(row.get("blocking_freq", 0.0) or 0.0)
    qp_ctx = row.get("upstream_qp_mean")
    qp_ctx = float(qp_ctx) if qp_ctx is not None and not (
        isinstance(qp_ctx, float) and np.isnan(qp_ctx)) else blk_own
    qp_raw = float(row.get("queue_pressure", 0.0) or 0.0)
    qp_eff = float(np.clip((qp_raw - 0.30) / 0.70, 0.0, 1.0))
    return {
        "cycle_time_deviation": float(np.clip(ct_dev / 25.0, 0.0, 1.0)),
        "queue_pressure": qp_eff,
        "downstream_starvation": float(np.clip(max(stv_ctx, stv_own) * 5.0,
                                               0.0, 1.0)),
        "upstream_blocking": float(np.clip(qp_ctx * 1.4, 0.0, 1.0)),
        "defect_rate": float(np.clip((row.get("defect_rate", 0.0) or 0.0) * 8.0,
                                     0.0, 1.0)),
        "neighbor_effect": float(np.clip(
            (max(float(row.get("upstream_ct_dev", 0.0) or 0.0), 0.0)
             + max(float(row.get("downstream_ct_dev", 0.0) or 0.0), 0.0)) / 40.0,
            0.0, 1.0)),
        "manual_failure_rate": float(np.clip(
            (float(row.get("manual_fail_rate")) * 8.0
             if row.get("manual_fail_rate") is not None
             and not (isinstance(row.get("manual_fail_rate"), float)
                      and np.isnan(row.get("manual_fail_rate"))) else 0.0),
            0.0, 1.0)),
    }


BASE_WEIGHTS = {
    "cycle_time_deviation": 0.25,
    "queue_pressure": 0.20,
    "downstream_starvation": 0.15,
    "upstream_blocking": 0.15,
    "defect_rate": 0.10,
    "neighbor_effect": 0.10,
    "manual_failure_rate": 0.05,
}

CLASS_WEIGHT_SHIFT = {
    "rich": {"cycle_time_deviation": 1.30, "queue_pressure": 1.00},
    "medium": {"cycle_time_deviation": 1.05, "queue_pressure": 1.15},
    "sparse": {"cycle_time_deviation": 0.85, "queue_pressure": 1.35},
}


def adaptive_weights(telemetry_class: str) -> dict[str, float]:
    w = dict(BASE_WEIGHTS)
    shift = CLASS_WEIGHT_SHIFT[telemetry_class]
    for k, f in shift.items():
        w[k] = w[k] * f
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def compute_bottleneck(row: pd.Series, telemetry_class: str) -> tuple[float, float, dict]:
    """Return (score 0-100, probability 0-1, evidence dict)."""
    ev = bottleneck_evidence(row)
    w = adaptive_weights(telemetry_class)
    score01 = sum(ev[k] * w[k] for k in w)
    score = round(float(score01 * 100.0), 2)
    prob = round(float(1.0 / (1.0 + np.exp(-(score01 - 0.42) * 9.0))), 4)
    prob = float(np.clip(prob, 0.0, 1.0))
    return score, prob, ev


def root_cause_adjust(feat: pd.DataFrame, scores: pd.Series, plant,
                      decay: float = 0.82) -> pd.Series:
    """Penalize downstream symptom stations when an upstream station explains them.

    If an upstream neighbor within 3 positions has a much higher score, the
    downstream station is more likely a *symptom* of flow starvation than the cause.
    """
    adj = scores.copy()
    pos = {sid: i for i, sid in enumerate(plant.stations)}
    by_station = scores.groupby(level="station_id").max() if hasattr(scores.index, "levels") else scores
    for sid in by_station.index:
        i = pos.get(sid)
        if i is None:
            continue
        window = plant.stations[max(0, i - 3):i]
        up_scores = [float(by_station.get(u, 0.0)) for u in window]
        if not up_scores:
            continue
        best_up = max(up_scores)
        own = float(by_station.get(sid, 0.0))
        if best_up > own + 12:
            factor = decay ** (1 + int(np.argmax(up_scores)))
            mask = scores.index.get_level_values("station_id") == sid
            adj[mask] = scores[mask] * factor
    return adj.clip(0.0, 100.0)


__all__ = ["compute_bottleneck", "adaptive_weights", "bottleneck_evidence",
           "root_cause_adjust"]
