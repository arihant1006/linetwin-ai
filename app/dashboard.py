"""DigitalTwin.ai control-room UI (Streamlit)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:
    st_autorefresh = None

import app.ui.components as components
from app.config.plant_config import SCENARIOS, SCENARIO_ORDER
from app.simulation.inject import apply_scenario, reset_simulation
from app.ui import leadership, manager, simulation, supervisor

st.set_page_config(
    page_title="DigitalTwin.ai",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

CSS = """
<style>
:root{--bg:#0e1117;--card:#171d26;--line:#232c3b;--accent:#22d3ee;
--txt:#e8edf4;--mut:#8b98ab;--dim:#66738a;}
.stApp{background:var(--bg);color:var(--txt);}
section[data-testid="stSidebar"]{background:#0b0f15;border-right:1px solid var(--line);}
section[data-testid="stSidebar"] *{color:var(--txt);}
h1,h2,h3{letter-spacing:.02em;}
.block-container{padding-top:1.1rem;padding-bottom:2rem;max-width:1500px;}
.kpi-card{background:var(--card);border:1px solid var(--line);border-radius:10px;
 padding:10px 14px;margin:0 4px 6px 0;height:100%;}
.kpi-label{font-size:10px;letter-spacing:.12em;color:var(--mut);
 text-transform:uppercase;margin-bottom:2px;}
.kpi-value{font-size:25px;font-weight:700;color:var(--txt);
 font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-variant-numeric:tabular-nums;
 line-height:1.15;}
.kpi-delta-up{color:#22c55e;font-size:12px;font-weight:600;}
.kpi-delta-down{color:#ef4444;font-size:12px;font-weight:600;}
.kpi-hint{color:var(--dim);font-size:11px;margin-top:1px;}
.sec-h{color:var(--accent);font-size:11px;letter-spacing:.18em;text-transform:uppercase;
 margin:8px 0 4px;font-weight:700;}
.why-box{font-family:ui-monospace,Menlo,monospace;background:#10151d;
 border:1px solid var(--line);border-radius:8px;padding:8px 10px;color:#93c5fd;
 font-size:12px;line-height:1.5;word-break:break-word;}
.alert-card{border-radius:8px;border-left:4px solid #475569;background:var(--card);
 padding:7px 11px;margin-bottom:6px;font-size:12.5px;color:var(--txt);}
.alert-card b{color:#fff;}
.rc-banner{background:linear-gradient(90deg,#2a1215 0%,#171d26 70%);
 border:1px solid #ef4444;border-radius:10px;padding:12px 18px;color:#fecaca;
 font-size:15px;margin-bottom:10px;}
.rc-banner .rc-big{font-size:19px;font-weight:800;color:#fff;}
.sim-chip{display:inline-block;border:1.5px solid #ef4444;color:#ef4444;
 border-radius:999px;padding:2px 12px;font-size:11px;font-weight:700;
 letter-spacing:.14em;margin-bottom:8px;}
.rec-card{background:var(--card);border:1px solid var(--line);border-radius:9px;
 padding:9px 12px;margin-bottom:7px;font-size:12.5px;}
.badge{display:inline-block;border-radius:999px;padding:1px 8px;font-size:10.5px;
 font-weight:700;letter-spacing:.05em;margin-right:6px;}
.impact-chip{background:var(--card);border:1px solid var(--line);border-left:4px solid var(--accent);
 border-radius:9px;padding:9px 12px;text-align:center;}
.impact-num{font-size:23px;font-weight:800;color:var(--accent);
 font-family:ui-monospace,Menlo,monospace;}
div[data-testid="stButton"] > button{padding:.28rem .65rem;font-size:12.5px;
 border:1px solid var(--line);border-radius:8px;color:var(--txt);
 background:#131924;font-variant-numeric:tabular-nums;}
div[data-testid="stButton"] > button:hover{border-color:var(--accent);color:var(--accent);}
div[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:9px;}
hr{border-color:var(--line);}
.sidebar-title{font-size:20px;font-weight:800;color:var(--accent);letter-spacing:.06em;}
.sidebar-sub{font-size:11.5px;color:var(--mut);margin-top:-4px;margin-bottom:10px;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

PERSONAS = ["Floor Supervisor", "Plant Manager", "Leadership", "What-If Simulator"]
SPEEDS = ["1x", "5x", "10x", "50x"]
LIVE_INTERVAL_MS = {"5x": 4000, "10x": 2500, "50x": 1200}

with st.sidebar:
    st.markdown('<div class="sidebar-title">DIGITALTWIN.AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sidebar-sub">Assembly Line Digital Twin</div>', unsafe_allow_html=True)

    label_to_key = {SCENARIOS[k].label: k for k in SCENARIO_ORDER}
    scenario_label = st.selectbox("Simulation Scenario", list(label_to_key.keys()), index=1)
    persona = st.radio("Persona", PERSONAS, index=0, horizontal=False)
    speed = st.selectbox("Simulation Speed", SPEEDS, index=0)
    live = st.checkbox("Live refresh", value=False)

    b1 = st.button("⚠️ Inject Failure", use_container_width=True, type="primary")
    b2 = st.button("♻️ Reset Simulation", use_container_width=True)
    b3 = st.button("🕒 Generate New Shift", use_container_width=True)

if b1:
    with st.spinner(f"Re-simulating window under failure '{scenario_label}' ..."):
        try:
            res = apply_scenario(scenario_key=label_to_key[scenario_label])
        except Exception as e:
            res = {"ok": False, "error": str(e)}
    if res.get("ok"):
        st.cache_data.clear()
        st.rerun()
    else:
        st.toast(f"Injection failed: {res.get('error', 'unknown error')}", icon="🚨")

if b2:
    with st.spinner("Resetting plant to normal production ..."):
        try:
            reset_simulation()
        except Exception as e:
            st.toast(f"Reset failed: {e}", icon="🚨")
            st.stop()
    st.cache_data.clear()
    st.rerun()

if b3:
    st.session_state["_flash"] = "Shift refreshed"
    st.cache_data.clear()
    st.rerun()

ctx = components.load_context(components.db_mtime())

meta_scen = ctx.get("active_scenario") or "normal"
sim_time = ctx.get("anchor_end")
scen_spec = SCENARIOS.get(meta_scen if meta_scen in SCENARIOS else "normal")
with st.sidebar:
    cap_time = sim_time if sim_time else "--:--:--"
    st.caption(f"⏱ Sim clock **{cap_time}**  \n🎬 Scenario: **{scen_spec.label}**")

if live and speed != "1x" and st_autorefresh is not None:
    st_autorefresh(interval=LIVE_INTERVAL_MS[speed], key="live_refresh")

if ctx["counts"]["telemetry"] == 0 or ctx["stations"].empty:
    st.warning("No data yet - run `python scripts/generate_data.py`")
    st.stop()

flash = st.session_state.pop("_flash", None)
if flash:
    st.toast(flash, icon="✅")

if persona == "Floor Supervisor":
    supervisor.render(ctx)
elif persona == "Plant Manager":
    manager.render(ctx)
elif persona == "Leadership":
    leadership.render(ctx)
else:
    simulation.render(ctx)
