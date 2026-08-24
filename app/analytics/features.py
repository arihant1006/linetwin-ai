"""Feature engineering from raw telemetry: contextual + local signal extraction."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.simulation.plant import PlantModel

BUCKET = "30min"
BUCKET_NUM_HOURS = 0.5

FEATURE_COLS = ["obs_n", "ct_deviation_pct", "mix_effect_pct", "ct_dev_ex_mix_pct",
                "upstream_ct_dev", "downstream_ct_dev", "queue_growth",
                "queue_pressure", "blocking_freq", "starvation_freq",
                "upstream_qp_mean", "downstream_stv_mean",
                "vehicle_mix_effect", "manual_fail_rate", "defect_rate",
                "vibration_z", "temperature_z", "torque_z", "motor_current_z",
                "sensor_coverage_obs", "throughput_vph", "avg_cycle_time",
                "avg_wait_sec"]


def bucketize(telemetry: pd.DataFrame) -> pd.DataFrame:
    df = telemetry.copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df["bucket_ts"] = df["ts"].dt.floor(BUCKET)
    return df


class BaselineStore:
    """Robust per-station baselines (median/MAD) from a reference telemetry window."""

    def __init__(self, telemetry_ref: pd.DataFrame):
        self.med: dict[tuple[str, str], float] = {}
        self.mad: dict[tuple[str, str], float] = {}
        self.ct_by_model: dict[tuple[str, str], float] = {}
        self._fit(telemetry_ref)

    def _fit(self, tel: pd.DataFrame) -> None:
        if tel.empty:
            return
        tel = bucketize(tel)
        for sid, sub in tel.groupby("station_id"):
            for col in ("cycle_time", "vibration", "temperature", "torque",
                        "motor_current"):
                vals = sub[col].dropna().values
                if len(vals) >= 20:
                    med = float(np.median(vals))
                    mad = float(np.median(np.abs(vals - med))) or 1e-6
                    self.med[(sid, col)] = med
                    self.mad[(sid, col)] = max(mad, 1e-3)
            mm = sub.groupby("vehicle_model")["cycle_time"].median()
            for model, v in mm.items():
                self.ct_by_model[(sid, model)] = float(v)

    def robust_z(self, sid: str, col: str, values: pd.Series) -> pd.Series:
        med = self.med.get((sid, col))
        if med is None or values.notna().sum() == 0:
            return pd.Series(0.0, index=values.index)
        mad = self.mad[(sid, col)]
        z = (values - med) / (1.4826 * mad)
        return z

    def expected_ct(self, sid: str, models: pd.Series,
                    fallback_target: float) -> pd.Series:
        out = [self.ct_by_model.get((sid, m), fallback_target) for m in models]
        return pd.Series(out, index=models.index)


def rank01(s: pd.Series) -> pd.Series:
    s = s.astype(float)
    valid = s.dropna()
    if valid.nunique() <= 1:
        return pd.Series(0.0, index=s.index)
    r = s.rank(pct=True)
    return ((r - r.min()) / max(r.max() - r.min(), 1e-9)).fillna(0.0)


def _mean_safe(v: np.ndarray) -> float:
    v = v[~np.isnan(v)]
    return float(v.mean()) if len(v) else 0.0


def compute_features(telemetry: pd.DataFrame, specs: pd.DataFrame, plant: PlantModel,
                     baseline: BaselineStore | None = None
                     ) -> tuple[pd.DataFrame, BaselineStore]:
    if baseline is None:
        baseline = BaselineStore(telemetry)
    if telemetry.empty:
        empty = pd.DataFrame(columns=["bucket_ts", "station_id"] + FEATURE_COLS)
        return empty.set_index(["bucket_ts", "station_id"]), baseline

    tel = bucketize(telemetry)
    ct_target = specs["cycle_time_target"].to_dict()
    rows = []

    for (bts, sid), sub in tel.groupby(["bucket_ts", "station_id"], sort=True):
        n = len(sub)
        target = ct_target.get(sid, 60.0)
        exp_ct = baseline.expected_ct(sid, sub["vehicle_model"], target)
        mix_effect = float((sub["cycle_time"] / exp_ct.clip(lower=1)).mean() - 1.0)
        raw_dev = float((sub["cycle_time"].mean() / target - 1.0) * 100.0)
        mean_wait = float(sub["wait_sec"].mean())
        starved = float((sub["machine_state"] == "STARVED").mean())
        blocked = float((sub["machine_state"] == "BLOCKED").mean())
        if "blocked" in sub.columns:
            blocked = float(((sub["machine_state"] == "BLOCKED")
                             | (sub["blocked"] == 1)).mean())
        manual_fail = float(1.0 - sub["manual_checklist"].mean()) \
            if sub["manual_checklist"].notna().any() else np.nan
        defect_rate = float(sub["defective_here"].mean())

        span_h = max((sub["ts"].max() - sub["ts"].min()).total_seconds() / 3600.0,
                     BUCKET_NUM_HOURS)
        throughput_vph = n / span_h

        def abs_mean_z(col: str) -> float | None:
            if sub[col].notna().sum() < 5:
                return None
            z = baseline.robust_z(sid, col, sub[col])
            return round(float(z.abs().mean()), 3)

        rows.append({
            "bucket_ts": bts, "station_id": sid, "obs_n": n,
            "ct_deviation_pct": round(raw_dev, 3),
            "mix_effect_pct": round(mix_effect * 100.0, 3),
            "ct_dev_ex_mix_pct": round(raw_dev - mix_effect * 50.0, 3),
            "queue_growth": round(mean_wait / 60.0, 3),
            "avg_wait_sec": round(mean_wait, 2),
            "starvation_freq": round(starved, 4),
            "blocking_freq": round(blocked, 4),
            "vehicle_mix_effect": round(mix_effect, 4),
            "manual_fail_rate": manual_fail,
            "defect_rate": round(defect_rate, 4),
            "vibration_z": abs_mean_z("vibration"),
            "temperature_z": abs_mean_z("temperature"),
            "torque_z": abs_mean_z("torque"),
            "motor_current_z": abs_mean_z("motor_current"),
            "sensor_coverage_obs": round(float(sub["sensor_available"].mean()), 3),
            "throughput_vph": round(throughput_vph, 3),
            "avg_cycle_time": round(float(sub["cycle_time"].mean()), 2),
        })

    feat = pd.DataFrame(rows)
    feat["queue_pressure"] = rank01(feat["queue_growth"])
    feat = add_context_columns(feat, plant)
    cols = ["bucket_ts", "station_id"] + FEATURE_COLS
    feat = feat[[c for c in cols if c in feat.columns]]
    return feat.set_index(["bucket_ts", "station_id"]), baseline


def add_context_columns(feat: pd.DataFrame, plant: PlantModel) -> pd.DataFrame:
    """Attach cross-station context: neighbor CT deviation, upstream queue
    pressure, downstream starvation - the signals that let sensor-poor stations
    be judged by their effect on flow."""
    if feat.empty:
        return feat
    piv_ct = feat.pivot_table(index="bucket_ts", columns="station_id",
                              values="ct_deviation_pct")
    piv_qp = feat.pivot_table(index="bucket_ts", columns="station_id",
                              values="queue_pressure")
    piv_stv = feat.pivot_table(index="bucket_ts", columns="station_id",
                               values="starvation_freq")
    pos = {sid: i for i, sid in enumerate(plant.stations)}
    up_vals, down_vals, up_qp, down_stv = [], [], [], []
    for r in feat.itertuples():
        bts, sid = r.bucket_ts, r.station_id
        i = pos.get(sid, 0)
        ups = [s for s in plant.stations[max(0, i - 3):i]]
        downs = [s for s in plant.stations[i + 1:i + 4]]
        if bts in piv_ct.index:
            row_ct = piv_ct.loc[bts]
            row_qp = piv_qp.loc[bts] if bts in piv_qp.index else None
            row_stv = piv_stv.loc[bts] if bts in piv_stv.index else None
            up_cols = [s for s in ups if s in piv_ct.columns]
            down_cols = [s for s in downs if s in piv_ct.columns]
            up_v = _mean_safe(row_ct[up_cols].values.astype(float))
            down_v = _mean_safe(row_ct[down_cols].values.astype(float)) \
                if down_cols else 0.0
            qp_up = _mean_safe(row_qp[[s for s in ups[-2:]
                                       if s in piv_qp.columns]].values.astype(float)) \
                if row_qp is not None else 0.0
            stv_down = _mean_safe(row_stv[[s for s in downs[:3]
                                           if s in piv_stv.columns]].values.astype(float)) \
                if row_stv is not None else 0.0
        else:
            up_v = down_v = qp_up = stv_down = 0.0
        up_vals.append(round(up_v, 3))
        down_vals.append(round(down_v, 3))
        up_qp.append(round(float(np.clip(qp_up, 0, 1)), 3))
        down_stv.append(round(float(np.clip(stv_down, 0, 1)), 4))
    feat = feat.copy()
    feat["upstream_ct_dev"] = up_vals
    feat["downstream_ct_dev"] = down_vals
    feat["upstream_qp_mean"] = up_qp
    feat["downstream_stv_mean"] = down_stv
    return feat
