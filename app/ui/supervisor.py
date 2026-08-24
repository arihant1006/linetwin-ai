"""Floor Supervisor persona page."""
from __future__ import annotations

import html

import numpy as np
import pandas as pd
import streamlit as st

from app.ui.components import (alerts_panel, kpi_card, station_detail_panel,
                              station_grid, top_bottleneck)


def _weighted_vph(metrics: pd.DataFrame) -> float:
    if metrics.empty:
        return 0.0
    v = pd.to_numeric(metrics.get("throughput_vph"), errors="coerce")
    w = pd.to_numeric(metrics.get("sensor_coverage"), errors="coerce").fillna(0.3).clip(lower=0.05)
    ok = v.notna()
    if not ok.any():
        return 0.0
    return float(np.average(v[ok], weights=w[ok]))


def render(ctx: dict) -> None:
    met, stations = ctx["metrics"], ctx["stations"]
    alerts = ctx["alerts"]
    counts = ctx["counts"]

    top_sid = top_bottleneck(met)
    if top_sid is not None:
        r = met.loc[top_sid]
        bp = float(r.get("bottleneck_prob", 0) or 0)
        if bp > 0.55:
            conf = float(r.get("confidence", 0) or 0)
            cov = float(r.get("sensor_coverage", 0) or 0)
            impact = round(-(bp * 20))
            st.markdown(
                f'<div class="rc-banner">🎯 PREDICTED BOTTLENECK &nbsp;'
                f'<span class="rc-big">{html.escape(str(top_sid))}</span>'
                f' &nbsp;|&nbsp; Confidence <b>{conf:.0f}%</b>'
                f' &nbsp;|&nbsp; Sensor Coverage <b>{cov * 100:.0f}%</b>'
                f' &nbsp;|&nbsp; Est. throughput impact <b>{impact:+d}%</b></div>',
                unsafe_allow_html=True)

    vph = _weighted_vph(met)
    n_bneck = int((pd.to_numeric(met.get("bottleneck_prob"), errors="coerce") > 0.5).sum()) \
        if not met.empty else 0
    healths = pd.to_numeric(met.get("health_score"), errors="coerce") if not met.empty else pd.Series(dtype=float)
    n_risk = int((healths < 60).sum())
    line_health = float(healths.mean()) if len(healths) else 0.0

    kpis = st.columns(6)
    with kpis[0]:
        kpi_card("Production Rate", f"{vph:.1f} vph", hint="coverage-weighted")
    with kpis[1]:
        kpi_card("Active Bottlenecks", str(n_bneck), hint="p>0.50",
                 delta=f"+{n_bneck}" if n_bneck else "0")
    with kpis[2]:
        kpi_card("Stations at Risk", str(n_risk), hint="health<60")
    with kpis[3]:
        kpi_card("Open Alerts", str(len(alerts)), hint="active")
    with kpis[4]:
        kpi_card("Vehicles in Line", f"{counts['vehicles']:,}", hint="total in window")
    with kpis[5]:
        kpi_card("Overall Line Health", f"{line_health:.0f}",
                 hint="mean of 40 stations")

    selected = st.session_state.get("selected_station") or top_sid
    station_grid(stations, met, selected=selected)

    left, right = st.columns([1.5, 1], gap="medium")
    with left:
        if selected:
            station_detail_panel(str(selected), ctx)
        else:
            st.info("No station state available.")
    with right:
        alerts_panel(alerts)
