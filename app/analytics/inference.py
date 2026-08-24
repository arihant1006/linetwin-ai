"""Digital-twin inference engine: fuses features into explainable station state."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.analytics.anomaly import (RichStationAnomalyModel, combine_anomaly,
                                   telemetry_anomaly_score, temporal_trend_score)
from app.analytics.bottleneck import compute_bottleneck
from app.analytics.health import (compute_confidence, compute_health,
                                  signal_agreement)
from app.config.plant_config import status_band
from app.simulation.plant import PlantModel


@dataclass
class StationState:
    station_id: str
    bucket_ts: str
    health_score: float
    anomaly_score: float
    bottleneck_score: float
    bottleneck_prob: float
    confidence: float
    status: str
    sensor_coverage: float
    throughput_vph: float
    cycle_time_deviation: float
    queue_pressure: float
    starvation_rate: float
    blocking_rate: float
    defect_rate: float
    is_root_cause_candidate: bool = False
    causes: list[str] = field(default_factory=list)
    explanation: list[dict] = field(default_factory=list)

    def why_lines(self) -> list[str]:
        return [f"{e['factor']}: {e['detail']}" for e in self.explanation]


def _fmt_sign(v: float) -> str:
    return ("+" if v >= 0 else "") + f"{v:.1f}"


class TwinInference:
    """Two-pass contextual inference.

    Pass 1 computes context-only health so neighbor information exists; pass 2
    blends neighbor health in, letting sensor-poor stations borrow strength
    from upstream/downstream behavior.
    """

    def __init__(self, specs: pd.DataFrame, plant: PlantModel, seed: int = 42):
        self.specs = specs
        self.plant = plant
        self.iforest = RichStationAnomalyModel(seed=seed)
        rich = specs.index[specs["telemetry_class"] == "rich"].tolist()
        self._rich_ids = list(rich)

    def fit(self, feat_history: pd.DataFrame) -> "TwinInference":
        try:
            self.iforest.fit(feat_history, self._rich_ids)
        except Exception:
            self.iforest = RichStationAnomalyModel(seed=42)
        return self

    def _station_anomaly(self, sid: str, tcls: str, hist: pd.DataFrame,
                         latest_row: pd.Series) -> tuple[float, float | None]:
        sz = telemetry_anomaly_score(latest_row)
        trend_ct = temporal_trend_score(hist, "ct_dev_ex_mix_pct") \
            if "ct_dev_ex_mix_pct" in hist.columns else 0.0
        trend_q = temporal_trend_score(hist, "queue_growth") \
            if "queue_growth" in hist.columns else 0.0
        trend = max(trend_ct, trend_q)
        if_sc = self.iforest.models.get(sid)
        if_sc_val = None
        if if_sc is not None:
            try:
                if_sc_val = self.iforest.score(sid, latest_row)
            except Exception:
                if_sc_val = None
        score, parts = combine_anomaly(sz, trend, if_sc_val, tcls)
        return score, sz

    def update(self, feat: pd.DataFrame) -> list[StationState]:
        """Score every station at its own most recent feature bucket.

        Scoring per-station (rather than one global timestamp) keeps the twin
        snapshot complete even when the anchor time falls near a shift change.
        """
        if feat is None or feat.empty:
            return []
        history_buckets = int(feat.index.get_level_values("bucket_ts").nunique())

        station_latest: dict[str, tuple[pd.Timestamp, pd.Series]] = {}
        station_hist: dict[str, pd.DataFrame] = {}
        for sid in feat.index.get_level_values("station_id").unique():
            try:
                h = feat.xs(sid, level="station_id").sort_index()
            except KeyError:
                continue
            if h.empty:
                continue
            station_latest[sid] = (h.index[-1], h.iloc[-1])
            station_hist[sid] = h.tail(8)

        pass1: dict[str, float] = {}
        for sid, (_bts, row) in station_latest.items():
            tcls = str(self.specs.loc[sid, "telemetry_class"])
            anom, _sz = self._station_anomaly(sid, tcls, station_hist[sid], row)
            h, _pen = compute_health(row, anom, None, tcls)
            pass1[sid] = h

        states: list[StationState] = []
        for sid, (bts, row) in station_latest.items():
            spec_row = self.specs.loc[sid]
            tcls = str(spec_row["telemetry_class"])
            nominal_cov = float(spec_row["sensor_coverage"])
            cov_obs = float(row.get("sensor_coverage_obs", nominal_cov) or nominal_cov)
            effective_cov = float(np.clip(nominal_cov * cov_obs, 0.02, 1.0))
            if tcls == "sparse":
                effective_cov = min(effective_cov, 0.60)

            anom, _sz = self._station_anomaly(sid, tcls, station_hist[sid], row)

            neighbors = self.plant.neighbors(sid, k=2)
            nb_vals = [pass1[n] for n in neighbors if n in pass1]
            neighbor_health = float(np.mean(nb_vals)) if nb_vals else None

            health, pen = compute_health(row, anom, neighbor_health, tcls)
            bscore, bprob, ev = compute_bottleneck(row, tcls)
            agreement = signal_agreement(row, anom)
            stress = float(np.clip(max((100.0 - health) / 60.0,
                                       bscore / 70.0), 0.0, 1.0))
            hist_df = station_hist.get(sid)
            obs_hist = int(round(float(hist_df["obs_n"].tail(4).mean()))) \
                if hist_df is not None and "obs_n" in hist_df.columns \
                else int(float(row.get("obs_n", 0)))
            conf = compute_confidence(effective_cov, obs_hist,
                                      agreement, history_buckets,
                                      stress_level=stress)
            causes = rank_causes(ev, pen)
            explanation = build_explanation(row, ev, pen, effective_cov, health,
                                            tcls)

            states.append(StationState(
                station_id=sid, bucket_ts=str(bts),
                health_score=health,
                anomaly_score=round(float(anom), 1),
                bottleneck_score=bscore,
                bottleneck_prob=float(np.clip(bprob, 0.0, 1.0)),
                confidence=conf,
                status=status_band(health),
                sensor_coverage=round(effective_cov, 3),
                throughput_vph=float(row.get("throughput_vph", 0.0)),
                cycle_time_deviation=float(row.get("ct_deviation_pct", 0.0)),
                queue_pressure=round(float(row.get("queue_pressure", 0.0)), 3),
                starvation_rate=float(row.get("starvation_freq", 0.0)),
                blocking_rate=float(row.get("blocking_freq", 0.0)),
                defect_rate=float(row.get("defect_rate", 0.0)),
                causes=causes,
                explanation=explanation,
            ))

        return apply_root_cause(states, self.plant)


def rank_causes(ev: dict[str, float], pen: dict[str, float]) -> list[str]:
    labels = {
        "cycle_time_deviation": "Cycle-time drift vs baseline",
        "queue_pressure": "Upstream queue build-up",
        "downstream_starvation": "Downstream starvation signature",
        "upstream_blocking": "Blocking downstream stations",
        "defect_rate": "Elevated defect creation",
        "neighbor_effect": "Neighbor/flow context abnormal",
        "manual_failure_rate": "Manual checklist failures rising",
        "sensor_anomaly": "Direct telemetry anomaly",
    }
    items = dict(ev)
    if pen.get("sensor_anomaly", 0) > 12:
        items["sensor_anomaly"] = min(pen["sensor_anomaly"] / 60.0, 1.0)
    ranked = sorted(items.items(), key=lambda kv: kv[1], reverse=True)
    out = [labels[k] for k, v in ranked[:3] if v > 0.25]
    if not out:
        out = ["No dominant stressor - within normal band"]
    return out


def build_explanation(row: pd.Series, ev: dict, pen: dict, coverage: float,
                      health: float, tcls: str) -> list[dict]:
    exp: list[dict] = []
    ct_dev = float(row.get("ct_dev_ex_mix_pct", 0.0) or 0.0)
    mix_pct = float(row.get("mix_effect_pct", 0.0) or 0.0)
    raw_pct = float(row.get("ct_deviation_pct", 0.0) or 0.0)
    exp.append({"factor": "Cycle-time deviation (mix-adjusted)",
                "detail": f"{_fmt_sign(ct_dev)}% vs target"
                          + (f" (raw {_fmt_sign(raw_pct)}%,"
                             f" model-mix explains ~{_fmt_sign(mix_pct)}%)"),
                "weight": round(min(max(ct_dev, 0) / 25, 1), 2)})
    qp = float(row.get("queue_pressure", 0.0) or 0.0)
    wait = float(row.get("avg_wait_sec", 0.0) or 0.0)
    exp.append({"factor": "Queue pressure",
                "detail": f"{qp:.0%} normalized (mean wait {wait:.0f}s)",
                "weight": round(qp, 2)})
    stv = float(row.get("starvation_freq", 0.0) or 0.0)
    stv_ctx = row.get("downstream_stv_mean")
    has_stv_ctx = stv_ctx is not None and not (isinstance(stv_ctx, float)
                                               and np.isnan(stv_ctx))
    exp.append({"factor": "Downstream starvation",
                "detail": (f"{stv:.1%} of own visits starved"
                           + (f"; downstream stations starving {float(stv_ctx):.0%}"
                              if has_stv_ctx else "")),
                "weight": round(min(max(stv, float(stv_ctx) if has_stv_ctx else 0)
                                    * 5, 1), 2)})
    blk = float(row.get("blocking_freq", 0.0) or 0.0)
    exp.append({"factor": "Upstream blocking",
                "detail": f"{blk:.1%} of visits blocked",
                "weight": round(min(blk * 6, 1), 2)})
    dr = float(row.get("defect_rate", 0.0) or 0.0)
    exp.append({"factor": "Defect creation rate",
                "detail": f"{dr:.1%} of units flagged at this station",
                "weight": round(min(dr * 8, 1), 2)})
    mf = row.get("manual_fail_rate")
    has_mf = mf is not None and not (isinstance(mf, float) and np.isnan(mf))
    exp.append({"factor": "Manual checklist",
                "detail": f"{float(mf):.1%} checks failed" if has_mf
                          else "no manual checklist data",
                "weight": round(min(float(mf) * 8, 1) if has_mf else 0.0, 2)})
    znames = {"vibration_z": "vibration", "temperature_z": "temperature",
              "torque_z": "torque", "motor_current_z": "motor current"}
    zs = [(znames[c], float(row[c])) for c in znames
          if row.get(c) is not None and not (isinstance(row.get(c), float)
                                             and np.isnan(row.get(c)))]
    if zs:
        top = max(zs, key=lambda kv: kv[1])
        exp.append({"factor": "Sensor z-scores",
                    "detail": f"strongest: {top[0]} |z|={top[1]:.1f}"
                              f" ({len(zs)} channels reporting)",
                    "weight": round(float(np.clip(top[1] / 5, 0, 1)), 2)})
    else:
        exp.append({"factor": "Sensor z-scores",
                    "detail": "no direct telemetry available - context-only inference",
                    "weight": 0.0})
    mode = ("strong contextual evidence despite sparse telemetry."
            if tcls == "sparse" and health < 60 else
            "signals broadly agree." if health < 60 else
            "all signals near baseline.")
    exp.append({"factor": "Inference mode",
                "detail": f"{tcls}-telemetry station, effective coverage "
                          f"{coverage:.0%}; {mode}",
                "weight": 0.0})
    return exp


def apply_root_cause(states: list[StationState], plant: PlantModel
                     ) -> list[StationState]:
    by_id = {s.station_id: s for s in states}
    ranked = sorted(states, key=lambda s: s.bottleneck_prob, reverse=True)
    root = ranked[0] if ranked else None
    if root and root.bottleneck_prob >= 0.35:
        root.is_root_cause_candidate = True
    for s in states:
        if s.station_id == (root.station_id if root else None):
            continue
        if s.bottleneck_prob < 0.30:
            continue
        ups = plant.upstream_chain(s.station_id, 4)
        if any(u in by_id and by_id[u].bottleneck_prob > s.bottleneck_prob + 0.08
               for u in ups):
            s.causes = ["Likely symptom of upstream constraint"] + s.causes[:2]
    return states
