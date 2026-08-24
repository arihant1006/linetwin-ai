"""Health scoring and confidence estimation."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.config.plant_config import status_band
from app.simulation.plant import PlantModel


def health_penalties(row: pd.Series, telemetry_class: str) -> dict[str, float]:
    """Penalty points (0-100 scale each, pre-weight) per evidence channel."""
    ct_dev = max(float(row.get("ct_dev_ex_mix_pct", 0.0) or 0.0), 0.0)
    pen: dict[str, float] = {}
    w_local = {"rich": 0.30, "medium": 0.34, "sparse": 0.36}[telemetry_class]
    pen["cycle_time_deviation"] = min(ct_dev / 25.0, 1.0) * 100 * w_local
    qp_raw = float(row.get("queue_pressure", 0.0) or 0.0)
    qp_eff = float(np.clip((qp_raw - 0.30) / 0.70, 0.0, 1.0))
    pen["queue_pressure"] = qp_eff * 100 * 0.16
    starv_own = float(row.get("starvation_freq", 0.0) or 0.0)
    stv_ctx = row.get("downstream_stv_mean")
    if stv_ctx is None or (isinstance(stv_ctx, float) and np.isnan(stv_ctx)):
        stv_ctx = 0.0
    pen["downstream_starvation"] = min(max(stv_ctx, starv_own) * 5.0, 1.0) * 100 * 0.12
    block = float(row.get("blocking_freq", 0.0) or 0.0)
    pen["upstream_blocking"] = min(block * 6.0, 1.0) * 100 * 0.10
    defect = float(row.get("defect_rate", 0.0) or 0.0)
    pen["defect_rate"] = min(defect * 10.0, 1.0) * 100 * 0.14
    mf = row.get("manual_fail_rate")
    if mf is not None and not (isinstance(mf, float) and np.isnan(mf)):
        pen["manual_checklist"] = min(float(mf) * 8.0, 1.0) * 100 * 0.08
    else:
        pen["manual_checklist"] = 4.0
    return pen


def compute_health(row: pd.Series, anomaly_score: float,
                   neighbor_health: float | None,
                   telemetry_class: str) -> tuple[float, dict]:
    """Health 0-100 from weighted penalties + neighbor smoothing.

    Sensor-rich stations let direct telemetry anomalies pull health down harder;
    sensor-poor stations rely on contextual channels.
    """
    pen = health_penalties(row, telemetry_class)
    anom_w = {"rich": 0.30, "medium": 0.22, "sparse": 0.10}[telemetry_class]
    pen["sensor_anomaly"] = float(anomaly_score) * anom_w
    total_penalty = sum(pen.values())
    health = float(np.clip(100.0 - total_penalty, 0.0, 100.0))
    if neighbor_health is not None:
        nb = float(neighbor_health)
        blend = {"rich": 0.06, "medium": 0.10, "sparse": 0.14}[telemetry_class]
        health = (1 - blend) * health + blend * nb
        pen["_neighbor_blend"] = round((health - (100.0 - total_penalty))
                                       * blend, 2)
    return round(float(np.clip(health, 0.0, 100.0)), 1), {k: round(v, 2)
                                                          for k, v in pen.items()}


def signal_agreement(row: pd.Series, anomaly_score: float) -> float:
    """Agreement between independent evidence streams -> 0..1.

    Only channels that actually report data participate; missing telemetry does
    not dilute agreement (that is what lets sensor-poor stations reach high
    confidence when their contextual signals converge).
    """
    def num(v) -> float | None:
        try:
            f = float(v)
            return None if np.isnan(f) else max(f, 0.0)
        except (TypeError, ValueError):
            return None

    ct = num(row.get("ct_dev_ex_mix_pct"))
    ct_n = min(ct / 20.0, 1.0) if ct is not None and ct > 0.03 else None
    qp = num(row.get("queue_pressure"))
    starv_own = num(row.get("starvation_freq"))
    stv_ctx = num(row.get("downstream_stv_mean"))
    blk = num(row.get("blocking_freq"))
    ctx_parts = [p for p in (
        qp, (max(stv_ctx or 0.0, starv_own or 0.0)) if (stv_ctx or starv_own) else None,
        blk) if p is not None]
    ctx_n = float(np.clip(np.mean(ctx_parts) * 2.2, 0, 1)) if ctx_parts else None
    anom_n = min(anomaly_score / 60.0, 1.0) if anomaly_score and anomaly_score > 3 \
        else None
    mf = num(row.get("manual_fail_rate"))
    mf_n = min(mf * 6.0, 1.0) if mf and mf > 0.02 else None
    dr = num(row.get("defect_rate"))
    dr_n = min(dr * 8.0, 1.0) if dr and dr > 0.02 else None

    vals = [v for v in (ct_n, ctx_n, anom_n, mf_n, dr_n) if v is not None]
    if not vals:
        return 0.30
    vals_sorted = sorted(vals, reverse=True)
    top = vals_sorted[:3]
    strength = float(np.mean(top))
    spread = (top[0] - np.mean(top)) if len(top) > 1 else 0.0
    consistency = float(np.clip(1.0 - spread * 1.2, 0.0, 1.0))
    breadth = min(1.0, 0.55 + 0.15 * len(vals))
    return float(np.clip(strength * 0.55 + consistency * 0.25 + breadth * 0.20,
                         0.0, 1.0))


def compute_confidence(sensor_coverage: float, obs_n: int, agreement: float,
                       history_buckets: int, stress_level: float = 0.0) -> float:
    """Confidence 0-100.

    Coverage matters, but convergent independent evidence (agreement) plus data
    volume can compensate - a sensor-poor station with strong contextual
    agreement earns HIGH confidence (the core prototype claim).
    """
    cov_term = float(np.clip(sensor_coverage, 0.02, 1.0)) ** 0.30
    vol_term = float(np.clip(obs_n / 25.0, 0.15, 1.0))
    hist_term = float(np.clip(history_buckets / 24.0, 0.20, 1.0))
    agree_term = float(np.clip(agreement, 0.0, 1.0))
    base = 100.0 * (0.34 * cov_term + 0.24 * vol_term * hist_term
                    + 0.42 * agree_term * vol_term)
    adjusted = base * (0.88 + 0.12 * float(np.clip(stress_level, 0.0, 1.0)))
    if agree_term >= 0.55:
        adjusted *= 1.14
        adjusted = min(adjusted, 99.0)
    return round(float(np.clip(adjusted, 3.0, 99.0)), 1)


def line_health(states: list[dict]) -> float:
    vals = [s["health_score"] for s in states if s.get("health_score") is not None]
    return round(float(np.mean(vals)), 1) if vals else 0.0


__all__ = ["compute_health", "compute_confidence", "signal_agreement",
           "health_penalties", "line_health", "status_band", "PlantModel"]
