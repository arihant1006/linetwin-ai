"""Plant Manager persona page: trends, propagation, matrix, Pareto, missing-data lab."""
from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import app.ui.components as components
from app.analytics.health import compute_confidence
from app.analytics.propagation import sankey_edges
from app.config.plant_config import STATUS_EMOJI, status_band
from app.ui.components import style_fig


def _weekly_throughput(hist: pd.DataFrame) -> go.Figure | None:
    if hist.empty:
        return None
    h = hist.copy()
    h["bucket_ts"] = pd.to_datetime(h["bucket_ts"])
    hourly = h.groupby(pd.Grouper(key="bucket_ts", freq="1h"))["throughput_vph"].mean()
    fig = go.Figure(go.Scatter(x=hourly.index, y=hourly.values, mode="lines",
                               line=dict(color="#22d3ee", width=2), name="line vph"))
    fig.add_hline(y=float(hourly.mean()), line_dash="dot", line_color="#66738a",
                  annotation_text="mean", annotation_font_size=10)
    fig.update_layout(title="Throughput — last 7 days (vehicles/hour, whole line)")
    return style_fig(fig, height=280)


def _ct_trend_by_area(ctx: dict, hist: pd.DataFrame) -> go.Figure | None:
    if hist.empty or ctx["stations"].empty:
        return None
    area_map = dict(zip(ctx["stations"]["station_id"], ctx["stations"]["area"]))
    h = hist.copy()
    h["area"] = h["station_id"].map(area_map)
    h = h.dropna(subset=["area"])
    h["bucket_ts"] = pd.to_datetime(h["bucket_ts"])
    fig = go.Figure()
    palette = {"Body Shop": "#22d3ee", "Paint Shop": "#a78bfa", "Final Assembly": "#f59e0b"}
    for area in ["Body Shop", "Paint Shop", "Final Assembly"]:
        sub = h[h["area"] == area]
        if sub.empty:
            continue
        s = sub.set_index("bucket_ts").sort_index()["avg_cycle_time"].resample("30min").mean()
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines", name=area,
                                 line=dict(width=1.8, color=palette[area])))
    fig.update_layout(title="Avg cycle time by area — last 24h")
    return style_fig(fig, height=280)


def _defect_sankey(defects: pd.DataFrame) -> None:
    chains = []
    for _, d in defects.iterrows():
        try:
            aff = json.loads(d.get("affected_stations_json") or "[]")
        except (TypeError, ValueError):
            aff = []
        if aff:
            chains.append({"affected_stations": list(aff),
                           "detected_station": d.get("detected_station")})
    edges = sankey_edges(chains)
    if not edges:
        st.info("No defect chains in current window.")
        return
    nodes: list[str] = []
    for a, b, _ in edges:
        for n in (a, b):
            if n not in nodes:
                nodes.append(n)
    idx = {n: i for i, n in enumerate(nodes)}
    fig = go.Figure(go.Sankey(
        node=dict(label=nodes, pad=12, thickness=14,
                  color="#22d3ee", line=dict(color="#0e1117", width=0.5)),
        link=dict(source=[idx[a] for a, _, _ in edges],
                  target=[idx[b] for _, b, _ in edges],
                  value=[int(n) for _, _, n in edges],
                  color="rgba(34,211,238,0.30)")))
    fig.update_layout(title="Defect propagation (origin → detection)")
    style_fig(fig, height=300)
    st.plotly_chart(fig, use_container_width=True)


def _station_matrix(ctx: dict) -> None:
    met = ctx["metrics"]
    if met.empty:
        st.info("No station metrics yet.")
        return
    rows = []

    def g(r, k, d=0.0):
        v = r.get(k, d)
        try:
            v = float(v)
        except (TypeError, ValueError):
            return d
        return v if pd.notna(v) else d

    for sid, r in met.iterrows():
        health = g(r, "health_score")
        band = status_band(health)
        rows.append({
            "Station": sid,
            "Health": round(health, 1),
            "Bottleneck Prob": round(g(r, "bottleneck_prob"), 2),
            "Defect Rate %": round(g(r, "defect_rate") * 100, 2),
            "Avg CT": round(g(r, "avg_cycle_time"), 1),
            "Coverage %": round(g(r, "sensor_coverage") * 100, 0),
            "Confidence": round(g(r, "confidence"), 0),
            "Status": f"{STATUS_EMOJI[band]} {band}",
        })
    df = pd.DataFrame(rows).sort_values("Health")

    def _health_color(v: float) -> str:
        if v >= 80:
            return "background-color: rgba(34,197,94,0.18)"
        if v >= 60:
            return "background-color: rgba(234,179,8,0.18)"
        if v >= 40:
            return "background-color: rgba(249,115,22,0.22)"
        return "background-color: rgba(239,68,68,0.25)"

    styler = (df.style
              .map(_health_color, subset=["Health"])
              .format({"Bottleneck Prob": "{:.2f}", "Avg CT": "{:.1f}s",
                       "Coverage %": "{:.0f}%", "Confidence": "{:.0f}%",
                       "Health": "{:.1f}"}))
    st.dataframe(styler, use_container_width=True, height=560)


def _pareto(met: pd.DataFrame) -> None:
    if met.empty:
        st.info("No station metrics yet.")
        return
    bp = pd.to_numeric(met.get("bottleneck_prob"), errors="coerce").fillna(0)
    qp = pd.to_numeric(met.get("queue_pressure"), errors="coerce").fillna(0)
    score = (bp * qp).sort_values(ascending=False).head(10).sort_values()
    fig = go.Figure(go.Bar(
        x=score.values, y=list(score.index), orientation="h",
        marker=dict(color=score.values, colorscale="OrRd"),
        text=[f"{v:.2f}" for v in score.values], textposition="auto",
        hoverinfo="x+y"))
    fig.update_layout(title="Bottleneck pressure — top 10 (prob × queue_pressure)",
                      showlegend=False)
    style_fig(fig, height=300)
    st.plotly_chart(fig, use_container_width=True)


def _missing_data_lab(stations: pd.DataFrame) -> None:
    st.caption("Prototype simulation – illustrative. Confidence curve uses the twin's "
               "`compute_confidence` formula (obs_n=40, agreement=0.8, history=48); "
               "contextual detection capability is held at full strength.")
    if stations.empty or "telemetry_class" not in stations.columns:
        st.info("Station specs unavailable.")
        return
    rich = stations[stations["telemetry_class"] == "rich"]
    rich_ids = list(rich.nlargest(6, "sensor_coverage").index) if len(rich) else []
    st.markdown(f"**Rich-sensor sample:** {', '.join(rich_ids) if rich_ids else '—'}")
    covs = [1.0, 0.7, 0.5, 0.3, 0.1]
    conf_curve = [compute_confidence(cov, obs_n=40, agreement=0.8, history_buckets=48)
                  for cov in covs]
    detect_curve = [100.0] * len(covs)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=covs, y=conf_curve, mode="lines+markers",
                             name="Predicted confidence", line=dict(color="#22d3ee")))
    fig.add_trace(go.Scatter(x=covs, y=detect_curve, mode="lines+markers",
                             name="Detection capability proxy (context-only)",
                             line=dict(color="#f59e0b", dash="dot")))
    fig.update_xaxes(tickformat=".0%", title="Synthetic sensor coverage")
    fig.update_yaxes(title="Score")
    fig.update_layout(title="Sensor coverage vs prediction confidence")
    style_fig(fig, height=280)
    st.plotly_chart(fig, use_container_width=True)


def render(ctx: dict) -> None:
    met = ctx["metrics"]
    mtime = components.db_mtime()
    hist168 = components.metric_history(mtime, 168)
    hist24 = components.metric_history(mtime, 24)

    t_thr, t_prop, t_mat, t_par, t_lab = st.tabs(
        ["📈 Throughput & Cycle Time", "🕸 Defect Propagation", "📋 Station Matrix",
         "🥇 Bottleneck Pareto", "🔬 Missing-Data Experiment"])

    with t_thr:
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            f1 = _weekly_throughput(hist168)
            if f1 is None:
                st.info("No metric history yet.")
            else:
                st.plotly_chart(f1, use_container_width=True)
        with c2:
            f2 = _ct_trend_by_area(ctx, hist24)
            if f2 is None:
                st.info("No metric history yet.")
            else:
                st.plotly_chart(f2, use_container_width=True)

    with t_prop:
        _defect_sankey(ctx["defects"])

    with t_mat:
        _station_matrix(ctx)

    with t_par:
        _pareto(met)

    with t_lab:
        stations_idx = ctx["stations"].set_index("station_id") \
            if not ctx["stations"].empty and "station_id" in ctx["stations"].columns \
            else ctx["stations"]
        _missing_data_lab(stations_idx)
