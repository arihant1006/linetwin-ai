"""Shared UI components: cached data loading, KPI cards, station grid, panels."""
from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.config.plant_config import AREAS, DB_PATH, STATUS_EMOJI, status_band
from app.data import database as db

STATION_COLS = ["station_id", "station_name", "area", "station_type", "sequence",
                "cycle_time_target", "cycle_time_std", "sensor_coverage",
                "telemetry_class", "criticality"]
METRIC_COLS = ["bucket_ts", "station_id", "throughput_vph", "avg_cycle_time",
               "ct_deviation_pct", "queue_length", "queue_pressure", "starvation_rate",
               "blocking_rate", "defect_rate", "sensor_coverage", "health_score",
               "anomaly_score", "bottleneck_score", "bottleneck_prob", "confidence",
               "status", "causes_json"]
ALERT_COLS = ["alert_id", "ts", "station_id", "severity", "kind", "message",
              "confidence", "sensor_coverage", "causes_json", "active"]
DEFECT_COLS = ["defect_id", "ts_origin", "origin_station", "defect_type", "severity",
               "propagation_probability", "affected_stations_json", "detected_station",
               "ts_detected", "scenario"]
REC_COLS = ["rec_id", "ts", "station_id", "issue", "evidence_json",
            "recommended_action", "expected_effect", "confidence", "simulation_only"]

STATE_COLORS = {"RUNNING": "#22c55e", "STARVED": "#eab308", "BLOCKED": "#f97316",
                "MAINTENANCE": "#94a3b8", "CHANGEOVER": "#38bdf8"}
NUMERIC_CHANNELS = ["cycle_time", "torque", "vibration", "temperature",
                    "motor_current", "pressure"]


def db_mtime() -> float:
    p = Path(os.environ.get("DIGITALTWIN_DB") or DB_PATH)
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _empty(cols: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=cols)


@st.cache_data(show_spinner=False)
def load_context(_mtime: float) -> dict:
    stations = _empty(STATION_COLS)
    met = _empty(METRIC_COLS)
    alerts = _empty(ALERT_COLS)
    defects = _empty(DEFECT_COLS)
    recs = _empty(REC_COLS)
    vehicles = 0
    telemetry_rows = 0
    active_scenario = "normal"
    anchor_end = None
    try:
        conn = db.get_conn()
        try:
            stations = db.load_stations(conn)
            if stations.empty:
                stations = _empty(STATION_COLS)
            else:
                stations = stations.reset_index()
            met = db.load_latest_metrics(conn)
            if met.empty:
                met = _empty(METRIC_COLS)
            else:
                met = met.set_index("station_id")
            alerts = db.load_alerts(conn, active_only=True, limit=100)
            if alerts.empty:
                alerts = _empty(ALERT_COLS)
            defects = db.load_defects(conn, limit=200)
            if defects.empty:
                defects = _empty(DEFECT_COLS)
            recs = db.load_recommendations(conn, limit=100)
            if recs.empty:
                recs = _empty(REC_COLS)
            vehicles = db.count_table(conn, "vehicles")
            telemetry_rows = db.count_table(conn, "telemetry")
            active_scenario = str(db.get_meta(conn, "active_scenario", default="normal"))
        finally:
            conn.close()
    except Exception:
        pass
    if not met.empty and "bucket_ts" in met.columns:
        anchor_end = str(met["bucket_ts"].max())
    return {"stations": stations, "metrics": met, "alerts": alerts,
            "defects": defects, "recommendations": recs,
            "counts": {"vehicles": int(vehicles), "telemetry": int(telemetry_rows)},
            "active_scenario": active_scenario, "anchor_end": anchor_end}


@st.cache_data(show_spinner=False)
def metric_history(_mtime: float, hours: float) -> pd.DataFrame:
    try:
        conn = db.get_conn()
        try:
            hist = db.load_metric_history(conn, hours=hours)
        finally:
            conn.close()
    except Exception:
        return _empty(METRIC_COLS)
    if hist.empty:
        return _empty(METRIC_COLS)
    return hist


@st.cache_data(show_spinner=False)
def station_telemetry(_mtime: float, sid: str) -> pd.DataFrame:
    try:
        conn = db.get_conn()
        try:
            tel = db.load_telemetry(conn, station_ids=[sid])
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()
    return tel.tail(200) if not tel.empty else pd.DataFrame()


def safe_loads(raw, default):
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def style_fig(fig: go.Figure, height: int = 260) -> go.Figure:
    fig.update_layout(template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=10, r=10, t=30, b=10), height=min(height, 320),
                      font=dict(size=11),
                      legend=dict(orientation="h", yanchor="top", y=-0.15,
                                  bgcolor="rgba(0,0,0,0)"))
    return fig


def status_color(status: str) -> str:
    return {"Healthy": "#22c55e", "Watch": "#eab308",
            "Degraded": "#f97316", "Critical": "#ef4444"}.get(str(status), "#64748b")


def kpi_card(label: str, value, delta: str | None = None, hint: str | None = None) -> None:
    delta_html = ""
    if delta:
        cls = "kpi-delta-up" if str(delta).strip().startswith("+") else \
              ("kpi-delta-down" if str(delta).strip().startswith("-") else "kpi-hint")
        arrow = "▲" if str(delta).startswith("+") else ("▼" if str(delta).startswith("-") else "")
        delta_html = f'<span class="{cls}">{arrow} {html.escape(str(delta))}</span>'
    hint_html = f'<div class="kpi-hint">{html.escape(str(hint))}</div>' if hint else ""
    st.markdown(
        f'<div class="kpi-card"><div class="kpi-label">{html.escape(label)}</div>'
        f'<div class="kpi-value">{html.escape(str(value))}</div>'
        f'{delta_html}{hint_html}</div>', unsafe_allow_html=True)


def top_bottleneck(metrics: pd.DataFrame):
    if metrics.empty or "bottleneck_prob" not in metrics.columns:
        return None
    m = metrics.sort_values("bottleneck_prob", ascending=False)
    return m.index[0] if len(m) else None


def station_grid(stations: pd.DataFrame, metrics: pd.DataFrame,
                 area_filter: str | None = None, selected: str | None = None) -> None:
    areas = [area_filter] if area_filter else AREAS
    midx = set(metrics.index) if not metrics.empty else set()
    for area in areas:
        sub = stations[stations["area"] == area] if not stations.empty else pd.DataFrame()
        ids = list(sub["station_id"]) if not sub.empty else []
        if not ids:
            continue
        names = dict(zip(sub["station_id"], sub["station_name"])) if not sub.empty else {}
        st.markdown(f'<div class="sec-h">{area.upper()} · {len(ids)} STATIONS</div>',
                    unsafe_allow_html=True)
        for i in range(0, len(ids), 8):
            chunk = ids[i:i + 8]
            cols = st.columns(8, gap="small")
            for col, sid in zip(cols[:len(chunk)], chunk):
                if sid in midx:
                    h = metrics.loc[sid].get("health_score")
                    band = status_band(float(h)) if pd.notna(h) else "Watch"
                    chip = f"{sid} {STATUS_EMOJI[band]} {float(h):.0f}" if pd.notna(h) \
                        else f"{sid} ⚪ --"
                else:
                    chip = f"{sid} ⚪ --"
                if selected == sid:
                    chip += " ◂"
                def _click(sid=sid):
                    st.session_state["selected_station"] = sid
                col.button(chip, key=f"chip-{sid}", on_click=_click,
                           use_container_width=True,
                           help=f"{names.get(sid, sid)}")


def station_detail_panel(sid: str, ctx: dict) -> None:
    met = ctx["metrics"]
    stations = ctx["stations"].set_index("station_id") if not ctx["stations"].empty \
        else pd.DataFrame()
    if sid not in met.index:
        st.info(f"No twin state yet for **{sid}**.")
        return
    row = met.loc[sid]
    name = stations.loc[sid, "station_name"] if sid in stations.index else sid
    area = stations.loc[sid, "area"] if sid in stations.index else ""

    def num(key, default=0.0):
        v = row.get(key, default)
        return float(v) if pd.notna(v) else default

    health = num("health_score", 50.0)
    conf = num("confidence", 0.0)
    bprob = num("bottleneck_prob", 0.0)
    cov = num("sensor_coverage", 0.0)

    st.markdown(f'<div class="sec-h">STATION DETAIL — {sid} · {name}'
                f'{f" ({area})" if area else ""}</div>', unsafe_allow_html=True)

    gcol, mcol = st.columns([1, 1.6], gap="small")
    with gcol:
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta", value=health,
            delta={"reference": 80, "increasing": {"color": "#22c55e"},
                   "decreasing": {"color": "#ef4444"}},
            number={"font": {"size": 30, "family": "monospace"}},
            gauge={"axis": {"range": [0, 100]},
                   "bar": {"color": "#22d3ee", "thickness": 0.28},
                   "steps": [{"range": [0, 40], "color": "rgba(239,68,68,.18)"},
                             {"range": [40, 60], "color": "rgba(249,115,22,.18)"},
                             {"range": [60, 80], "color": "rgba(234,179,8,.18)"},
                             {"range": [80, 100], "color": "rgba(34,197,94,.18)"}],
                   "threshold": {"line": {"color": "#e8edf4", "width": 1},
                                 "value": 80}}))
        style_fig(fig, height=195).update_layout(margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with mcol:
        c1, c2 = st.columns(2)
        c1.markdown(f'<div class="kpi-card"><div class="kpi-label">Confidence</div>'
                    f'<div class="kpi-value">{conf:.0f}%</div></div>', unsafe_allow_html=True)
        c2.markdown(f'<div class="kpi-card"><div class="kpi-label">Bottleneck prob</div>'
                    f'<div class="kpi-value">{bprob * 100:.0f}%</div></div>',
                    unsafe_allow_html=True)
        c3, c4 = st.columns(2)
        c3.markdown(f'<div class="kpi-card"><div class="kpi-label">Sensor coverage</div>'
                    f'<div class="kpi-value">{cov * 100:.0f}%</div></div>',
                    unsafe_allow_html=True)
        ct_dev = row.get("ct_deviation_pct", 0.0)
        ct_dev = float(ct_dev) if pd.notna(ct_dev) else 0.0
        c4.markdown(f'<div class="kpi-card"><div class="kpi-label">CT deviation</div>'
                    f'<div class="kpi-value">{ct_dev:+.1f}%</div></div>',
                    unsafe_allow_html=True)

    target = float(stations.loc[sid, "cycle_time_target"]) if sid in stations.index else None
    avg_ct = row.get("avg_cycle_time")
    if target and pd.notna(avg_ct):
        bar = go.Figure(go.Bar(
            x=[target, float(avg_ct)], y=["Target", "Actual"], orientation="h",
            marker_color=["rgba(51,65,85,0.55)", "#22d3ee"], text=[f"{target:.0f}s", f"{avg_ct:.0f}s"],
            textposition="auto"))
        bar.update_layout(showlegend=False)
        style_fig(bar, height=120)
        st.plotly_chart(bar, use_container_width=True)

    causes = safe_loads(row.get("causes_json"), [])
    if causes:
        st.markdown("**Root-cause factors**")
        for c in list(causes)[:5]:
            st.markdown(f"&nbsp;&nbsp;• {html.escape(str(c))}", unsafe_allow_html=True)

    why_parts = []
    if ct_dev:
        why_parts.append(f"{ct_dev:+.0f}% cycle-time deviation")
    qp = row.get("queue_pressure", 0.0)
    if pd.notna(qp) and float(qp):
        why_parts.append(f"{float(qp) * 100:+.0f}% queue pressure")
    sr = row.get("starvation_rate", 0.0)
    if pd.notna(sr) and float(sr):
        why_parts.append(f"{float(sr) * 100:.0f}% starvation")
    br = row.get("blocking_rate", 0.0)
    if pd.notna(br) and float(br):
        why_parts.append(f"{float(br) * 100:.0f}% blocking")
    dr = row.get("defect_rate", 0.0)
    if pd.notna(dr) and float(dr):
        why_parts.append(f"{float(dr) * 100:.1f}% defect rate")
    why_parts.append(f"{cov * 100:.0f}% sensor coverage")
    status = status_band(health)
    st.markdown(
        f'<div class="why-box"><b style="color:#22d3ee">WHY {status.upper()}:</b><br>'
        f"{' / '.join(html.escape(p) for p in why_parts)}</div>", unsafe_allow_html=True)

    tel = station_telemetry(db_mtime(), sid)
    if tel.empty:
        st.info("No recent raw telemetry for this station.")
        return
    tel = tel.copy()
    tel["ts_dt"] = pd.to_datetime(tel["ts"])

    states = tel.dropna(subset=["machine_state"])
    if not states.empty:
        order = ["RUNNING", "STARVED", "BLOCKED", "MAINTENANCE", "CHANGEOVER"]
        smap = {s: i for i, s in enumerate(order)}
        strip = go.Figure(go.Scatter(
            x=states["ts_dt"], y=states["machine_state"].map(smap), mode="markers",
            marker=dict(size=7, color=states["machine_state"].map(STATE_COLORS)),
            hovertext=states["machine_state"], showlegend=False))
        strip.update_yaxes(tickvals=list(range(len(order))),
                           ticktext=order, autorange="reversed")
        strip.update_layout(title="Machine state (recent)")
        style_fig(strip, height=150)
        st.plotly_chart(strip, use_container_width=True)

    chans = [c for c in NUMERIC_CHANNELS
             if c in tel.columns and pd.to_numeric(tel[c], errors="coerce").notna().any()]
    if chans:
        lines = go.Figure()
        palette = ["#22d3ee", "#a78bfa", "#f59e0b", "#22c55e", "#ef4444", "#38bdf8"]
        for i, ch in enumerate(chans):
            y = pd.to_numeric(tel[ch], errors="coerce")
            lines.add_trace(go.Scatter(x=tel["ts_dt"], y=y, mode="lines", name=ch,
                                       line=dict(width=1.4, color=palette[i % 6])))
        lines.update_layout(title="Sensor channels (raw)")
        style_fig(lines, height=230)
        st.plotly_chart(lines, use_container_width=True)


def alerts_panel(alerts: pd.DataFrame, max_n: int = 12) -> None:
    st.markdown('<div class="sec-h">ACTIVE ALERTS</div>', unsafe_allow_html=True)
    if alerts.empty:
        st.info("No active alerts. Line is quiet.")
        return
    sev_style = {
        "CRITICAL": ("#ef4444", "🚨"),
        "WARNING": ("#eab308", "⚠️"),
        "INFO": ("#64748b", "ℹ️"),
    }
    for _, a in alerts.head(max_n).iterrows():
        color, icon = sev_style.get(str(a.get("severity")), sev_style["INFO"])
        conf = a.get("confidence")
        cov = a.get("sensor_coverage")
        conf_s = f"{float(conf) * 100:.0f}%" if pd.notna(conf) else "--"
        cov_s = f"{float(cov) * 100:.0f}%" if pd.notna(cov) else "--"
        causes = safe_loads(a.get("causes_json"), [])
        cause_s = " · ".join(str(c) for c in causes[:3]) if causes else ""
        msg = html.escape(str(a.get("message", "")))
        sid = html.escape(str(a.get("station_id", "")))
        st.markdown(
            f'<div class="alert-card" style="border-left-color:{color}">'
            f'{icon} <b>{sid}</b> — {msg}<br>'
            f'<span style="color:#66738a">conf {conf_s} · coverage {cov_s}'
            + (f' &nbsp;|&nbsp; <span style="color:#93c5fd">{html.escape(cause_s)}</span>'
               if cause_s else "")
            + "</span></div>", unsafe_allow_html=True)
