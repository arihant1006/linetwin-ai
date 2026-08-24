"""What-If / Recommendation Simulator page (simulation only, no PLC writes)."""
from __future__ import annotations

import html
import json
from datetime import datetime
from uuid import uuid4

import pandas as pd
import streamlit as st

import app.ui.components as components
from app.analytics.whatif import ACTIONS, PLCAdapter, simulate_action
from app.data import database as db
from app.ui.components import kpi_card, top_bottleneck

SNIPPET = '''\
from app.analytics.whatif import PLCAdapter
PLCAdapter().write("start_line")   # -> RuntimeError:
# "PLC writes disabled in prototype simulation"'''


def _states_from_metrics(met: pd.DataFrame) -> list[dict]:
    states = []
    for sid, r in met.iterrows():
        def g(k, d):
            v = r.get(k, d)
            try:
                v = float(v)
            except (TypeError, ValueError):
                return d
            return v if pd.notna(v) else d
        states.append({
            "station_id": str(sid),
            "avg_cycle_time": g("avg_cycle_time", 60.0),
            "sensor_coverage": g("sensor_coverage", 0.5),
            "health_score": g("health_score", 70.0),
            "bottleneck_prob": g("bottleneck_prob", 0.1),
        })
    return states


def _rec_card(r) -> None:
    try:
        evidence = json.loads(r.get("evidence_json") or "[]")
    except (TypeError, ValueError):
        evidence = []
    conf = float(r.get("confidence", 0) or 0) * 100
    ev = " · ".join(str(e) for e in evidence[:3]) if evidence else ""
    st.markdown(
        f'<div class="rec-card">'
        f'<span class="badge" style="background:#0e749055;color:#67e8f9">'
        f'{html.escape(str(r.get("station_id", "")))}</span>'
        f'<span class="badge" style="background:#33415588;color:#cbd5e1">SIM ONLY</span>'
        f'<span class="badge" style="background:#1d4ed855;color:#bfdbfe">conf {conf:.0f}%</span>'
        f'<br><b>{html.escape(str(r.get("issue", "")))}</b><br>'
        f'<span style="color:#8b98ab">→ {html.escape(str(r.get("recommended_action", "")))}'
        f' &nbsp;·&nbsp; {html.escape(str(r.get("expected_effect", "")))}</span>'
        + (f'<br><span style="color:#66738a;font-size:11px">{html.escape(ev)}</span>' if ev else "")
        + '</div>', unsafe_allow_html=True)


def render(ctx: dict) -> None:
    met = ctx["metrics"]
    recs = ctx["recommendations"]

    st.markdown('<span class="sim-chip">⚠ SIMULATION ONLY — NO PLC WRITE</span>',
                unsafe_allow_html=True)

    left, right = st.columns([1.1, 1.6], gap="medium")

    with left:
        st.markdown('<div class="sec-h">TWIN RECOMMENDATIONS</div>', unsafe_allow_html=True)
        if recs.empty:
            st.info("No open recommendations.")
        else:
            for _, r in recs.head(8).iterrows():
                _rec_card(r)

    default_sid = top_bottleneck(met) or (met.index[0] if not met.empty else None)
    sids = list(met.index) if not met.empty else []

    with right:
        st.markdown('<div class="sec-h">WHAT-IF ACTION</div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([1, 1.3, 1])
        with c1:
            sid = st.selectbox("Station", sids,
                               index=sids.index(default_sid) if default_sid in sids else 0)
        with c2:
            action_key = st.selectbox("Action", list(ACTIONS.keys()),
                                      format_func=lambda k: ACTIONS[k])
        with c3:
            st.write("")
            run_btn = st.button("▶ Simulate Recommendation", type="primary",
                                use_container_width=True)

        if run_btn and not met.empty:
            out = simulate_action(_states_from_metrics(met), str(sid), action_key)
            if out is None:
                st.error("Simulation failed for this station/action.")
            else:
                b, a = out["before"], out["after"]
                imp = out["projected_improvement_pct"]
                arrow = "▲" if imp >= 0 else "▼"
                color = "#22c55e" if imp >= 0 else "#ef4444"
                st.markdown(
                    f'**{out["action_label"]}** — projected line effect: '
                    f'<span style="color:{color};font-weight:800">{arrow} {abs(imp):.1f}%</span>',
                    unsafe_allow_html=True)
                bc, mid, ac = st.columns([1, 0.25, 1])
                with bc:
                    st.markdown("**BEFORE**")
                    kpi_card("Throughput", f'{b["throughput_vph"]:.1f} vph')
                    kpi_card("Health", f'{b["health"]:.0f}')
                    kpi_card("Bottleneck prob", f'{b["bottleneck_prob"] * 100:.0f}%')
                with mid:
                    st.markdown("<div style='height:52px'></div>"
                                "<div style='font-size:26px;color:#22d3ee'>→</div>",
                                unsafe_allow_html=True)
                with ac:
                    st.markdown("**AFTER (projected)**")
                    kpi_card("Throughput", f'{a["throughput_vph"]:.1f} vph',
                             delta=f"{imp:+.1f}%" if imp else None)
                    kpi_card("Health", f'{a["projected_health"]:.0f}',
                             delta=f'{a["projected_health"] - b["health"]:+.0f}')
                    kpi_card("Bottleneck prob",
                             f'{a["projected_bottleneck_prob"] * 100:.0f}%')

                try:
                    conn = db.get_conn()
                    try:
                        db.insert_simulation_run(conn, {
                            "run_id": str(uuid4()),
                            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "station_id": str(sid),
                            "action": action_key,
                            "before": b, "after": a,
                            "projected_improvement_pct": imp,
                            "note": "SIMULATION ONLY"})
                    finally:
                        conn.close()
                    st.toast("Run logged to simulation_runs", icon="🧪")
                except Exception as e:
                    st.warning(f"Could not persist run: {e}")

        with st.expander("🔒 Integration boundary"):
            st.code(SNIPPET, language="python")
            if st.button("⚡ Attempt PLC Write"):
                try:
                    PLCAdapter().write("test")
                except RuntimeError as e:
                    st.error(f"RuntimeError: {e}")
