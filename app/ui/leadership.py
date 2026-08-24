"""Leadership persona page: business KPIs, impact chips, ROI calculator."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import app.ui.components as comp
from app.ui.components import kpi_card

DOWNTIME_COST_HR = 220_000
DEFECT_COST = 14_000
VEHICLE_VALUE = 850_000


def _fmt_inr(v: float) -> str:
    v = float(v)
    if abs(v) >= 1e7:
        return f"₹{v / 1e7:.2f} Cr"
    if abs(v) >= 1e5:
        return f"₹{v / 1e5:.1f} L"
    return f"₹{v:,.0f}"


def render(ctx: dict) -> None:
    met = ctx["metrics"]
    hist24 = comp.metric_history(comp.db_mtime(), 24)

    if met.empty:
        vph = 0.0
        defect_pct = 0.0
    else:
        v = pd.to_numeric(met.get("throughput_vph"), errors="coerce")
        w = pd.to_numeric(met.get("sensor_coverage"), errors="coerce").fillna(0.3).clip(lower=0.05)
        ok = v.notna()
        vph = float(np.average(v[ok], weights=w[ok])) if ok.any() else 0.0
        defect_pct = float(pd.to_numeric(met.get("defect_rate"), errors="coerce").mean() * 100)

    veh_today = vph * 16.0
    starve_min_day = 0.0
    if hist24 is not None and not hist24.empty:
        h = hist24.copy()
        h["bucket_ts"] = pd.to_datetime(h["bucket_ts"])
        per_bucket = h.groupby("bucket_ts")["starvation_rate"].mean()
        starve_min_day = float((per_bucket * 60.0).sum())
    downtime_hrs_day = starve_min_day / 60.0
    defects_per_year = (defect_pct / 100.0) * veh_today * 300
    annual_loss = (downtime_hrs_day * 300 * DOWNTIME_COST_HR
                   + defects_per_year * DEFECT_COST)

    st.markdown('<div class="sec-h">PLANT AT A GLANCE</div>', unsafe_allow_html=True)
    k = st.columns(4)
    with k[0]:
        kpi_card("Line Throughput Today", f"{veh_today:,.0f} veh",
                 hint=f"{vph:.1f} vph × 16h shift")
    with k[1]:
        kpi_card("Defect Rate", f"{defect_pct:.2f}%", hint="fleet mean, current window")
    with k[2]:
        kpi_card("Downtime Proxy", f"{starve_min_day:,.0f} min",
                 hint="starved minutes / 24h")
    with k[3]:
        kpi_card("Estimated Annual Loss", _fmt_inr(annual_loss),
                 hint=f"{downtime_hrs_day:.1f} down-hrs/day × 300d + defects")

    st.markdown('<div class="sec-h">PROJECTED IMPACT OF DIGITAL TWIN '
                '<span style="color:#66738a;text-transform:none;letter-spacing:0">'
                '(illustrative)</span></div>', unsafe_allow_html=True)
    c = st.columns(3)
    for col, pct, lbl in [(c[0], "32%", "Potential downtime reduction"),
                          (c[1], "41%", "Defect reduction"),
                          (c[2], "9%", "Throughput increase")]:
        with col:
            st.markdown(f'<div class="impact-chip"><div class="impact-num">{pct}</div>'
                        f'<div style="color:#8b98ab;font-size:11px;margin-top:2px">{lbl}'
                        '</div></div>', unsafe_allow_html=True)

    st.markdown('<div class="sec-h">ROI CALCULATOR</div>', unsafe_allow_html=True)
    i1, i2, i3 = st.columns(3)
    i4, i5, i6 = st.columns(3)
    with i1:
        veh_day = st.number_input("Vehicles / day", 10, 5000, int(max(veh_today, 480)), step=10)
    with i2:
        prod_days = st.number_input("Production days / year", 50, 365, 300)
    with i3:
        val_veh = st.number_input("Value / vehicle (₹)", 100_000, 5_000_000, VEHICLE_VALUE, step=25_000)
    with i4:
        dt_cost = st.number_input("Downtime cost / hour (₹)", 10_000, 5_000_000,
                                  DOWNTIME_COST_HR, step=10_000)
    with i5:
        def_cost = st.number_input("Defect cost (₹)", 500, 500_000, DEFECT_COST, step=500)
    with i6:
        dep_cost = st.number_input("Deployment cost (₹)", 100_000, 100_000_000,
                                   4_200_000, step=100_000)

    dt_hours_saved_yr = downtime_hrs_day * prod_days * 0.32
    defects_prevented_yr = defects_per_year * 0.41
    extra_vehicles_yr = veh_day * prod_days * 0.09
    benefit = (dt_hours_saved_yr * dt_cost
               + defects_prevented_yr * def_cost
               + extra_vehicles_yr * val_veh)
    roi_pct = (benefit - dep_cost) / dep_cost * 100.0 if dep_cost > 0 else 0.0
    payback_months = dep_cost / (benefit / 12.0) if benefit > 0 else float("inf")

    o1, o2, o3, o4 = st.columns(4)
    with o1:
        kpi_card("Annual Benefit", _fmt_inr(benefit),
                 hint=f"{extra_vehicles_yr:.0f} extra veh · {defects_prevented_yr:.0f} "
                      f"fewer defects")
    with o2:
        kpi_card("Net Year-1", _fmt_inr(benefit - dep_cost))
    with o3:
        kpi_card("ROI", f"{roi_pct:,.0f}%",
                 delta=f"+{roi_pct:,.0f}%" if roi_pct >= 0 else f"{roi_pct:,.0f}%")
    with o4:
        pb = f"{payback_months:.1f} mo" if np.isfinite(payback_months) else "—"
        kpi_card("Payback", pb)

    st.markdown(
        '<div class="rc-banner" style="border-color:#eab308;'
        'background:linear-gradient(90deg,#2a230d,#171d26 70%);color:#fef3c7;font-size:13px">'
        '⚠️ Illustrative prototype estimate — simulated numbers, not real industrial claims.'
        '</div>', unsafe_allow_html=True)
