"""Anomaly scoring: rolling robust z-scores + optional IsolationForest (rich stations)."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.analytics.features import BaselineStore

SENSOR_Z_COLS = ["vibration_z", "temperature_z", "torque_z", "motor_current_z"]
MIN_SAMPLES_IFOREST = 120


def telemetry_anomaly_score(row: pd.Series) -> float | None:
    """Mean absolute robust z across available sensor channels (None if no sensors)."""
    vals = [row[c] for c in SENSOR_Z_COLS if c in row.index and row[c] is not None
            and not (isinstance(row[c], float) and np.isnan(row[c]))]
    if not vals:
        return None
    return float(np.clip(np.mean(vals), 0.0, None))


def temporal_trend_score(feat_station: pd.DataFrame, col: str = "ct_dev_ex_mix_pct",
                         window: int = 6) -> float:
    """Positive-trend magnitude of a feature over recent buckets (0..1)."""
    s = feat_station[col].astype(float).dropna()
    if len(s) < 3:
        return 0.0
    recent = s.tail(window)
    x = np.arange(len(recent))
    if np.std(x) == 0:
        return 0.0
    slope = float(np.polyfit(x, recent.values, 1)[0])
    scale = max(float(recent.std()), 1.0)
    return float(np.clip(abs(slope) / (2.0 * scale + 1e-9), 0.0, 1.0))


class RichStationAnomalyModel:
    """Auxiliary IsolationForest for stations with enough multivariate history."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.models: dict[str, IsolationForest] = {}
        self.cols = ["ct_deviation_pct", "queue_growth", "vibration_z",
                     "temperature_z", "torque_z", "motor_current_z"]

    def fit(self, feat: pd.DataFrame, station_ids: list[str]) -> None:
        for sid in station_ids:
            try:
                sub = feat.xs(sid, level="station_id")
            except KeyError:
                continue
            X = sub[[c for c in self.cols if c in sub.columns]].apply(
                pd.to_numeric, errors="coerce")
            X = X.dropna(axis=1, how="all").fillna(0.0)
            if len(X) < MIN_SAMPLES_IFOREST or X.shape[1] < 3:
                continue
            model = IsolationForest(n_estimators=60, contamination=0.08,
                                    random_state=self.seed)
            model.fit(X.values)
            self.models[sid] = model

    def score(self, sid: str, row: pd.Series) -> float | None:
        model = self.models.get(sid)
        if model is None:
            return None
        X = np.array([[float(row.get(c, 0.0) or 0.0)
                       for c in model.feature_names_in_]], dtype=float) \
            if hasattr(model, "feature_names_in_") else \
            np.array([[float(row.get(c, 0.0) or 0.0) for c in self.cols]])
        raw = float(-model.decision_function(X)[0])
        return float(np.clip(raw * 5.0, 0.0, 1.0))


def combine_anomaly(sensor_z_mean: float | None, trend: float,
                    iforest_score: float | None,
                    telemetry_class: str) -> tuple[float, dict]:
    """Fuse anomaly evidence into 0-100 with per-source breakdown."""
    w_sensor = {"rich": 0.55, "medium": 0.30, "sparse": 0.10}[telemetry_class]
    w_trend = {"rich": 0.25, "medium": 0.40, "sparse": 0.50}[telemetry_class]
    w_if = 0.20 if (telemetry_class == "rich" and iforest_score is not None) else 0.0
    if sensor_z_mean is None:
        w_trend += w_sensor
        w_sensor = 0.0
    total_w = max(w_sensor + w_trend + w_if, 1e-9)
    parts: dict[str, float] = {}
    if w_sensor > 0 and sensor_z_mean is not None:
        s_val = float(np.clip(sensor_z_mean / 4.0, 0.0, 1.0)) * 100.0
        parts["sensor_z"] = s_val * w_sensor / total_w
    t_val = float(np.clip(trend, 0.0, 1.0)) * 100.0
    parts["temporal_trend"] = t_val * w_trend / total_w
    if w_if > 0 and iforest_score is not None:
        parts["isolation_forest"] = float(np.clip(iforest_score, 0.0, 1.0)) * 100.0 \
            * w_if / total_w
    final = float(np.clip(sum(parts.values()), 0.0, 100.0))
    return round(final, 2), {k: round(v, 2) for k, v in parts.items()}
