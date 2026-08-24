# DigitalTwin.ai

A local, simulation-only digital twin that infers station health and bottlenecks across a 40-station automotive assembly line - including where sensors are missing or dark.

> Prototype. All data is simulated and stored locally in SQLite. Nothing here touches real plant equipment.

## Problem

Industrial assembly lines have uneven instrumentation: in this plant roughly **40% of stations have rich telemetry, 35% medium, and 25% sparse**. Traditional monitoring thresholds only work where sensors exist - sensor-poor stations are blind spots, and a dying sensor on a degrading machine makes it look *healthier* than it is.

## Solution

Context-aware digital-twin inference. For every station - instrumented or not - the twin estimates health, anomaly, and bottleneck scores from:

- local cycle-time deviation vs. model-aware baselines
- upstream/downstream flow and queue pressure
- starvation/blocking rates and wait times
- defect rates and manual checklist outcomes
- neighbor health and historical behavior

Each score ships with an explicit **confidence** value (tied to effective sensor coverage) and an explainability **"Why?"** panel listing every contributing factor and its weight. The line keeps working even when a station's sensors go dark.

## Architecture

```
Simulation Engine          Data Processing           Digital Twin Inference
(vehicles, sensors,   -->  (validation, features,  -->  (health, anomaly, bottleneck,
failure injection,         baselines, missing-data       confidence, root cause,
defect propagation)        handling)                     explainability)
                                                          |
                                                          v
              Streamlit dashboards  <--  SQLite store (telemetry, metrics,
              (multi-persona UI)               alerts, defects, recommendations)

Layering: OBSERVE -> INFER -> RECOMMEND -> SIMULATE
CONTROL is deliberately impossible: PLCAdapter.write() raises RuntimeError by design.
```

## Features

- **40-station mixed-model plant**: Body Shop B01-B15, Paint Shop P01-P10, Final Assembly F01-F15
- **4 vehicle models** (Model-A/B/C/D) with distinct cycle-time multipliers and torque signatures
- **Uneven sensor coverage**: rich / medium / sparse telemetry classes (40% / 35% / 25% of stations)
- **Intermittent sensor outages** plus per-record random dropouts
- **Multi-causal failure scenarios**: mechanical degradation, sensor failure, material shortage, model-mix shift, quality-defect propagation, human/manual issues, combined failures
- **Weighted adaptive bottleneck scoring** - weights shift toward contextual signals (flow, queues, neighbors) as direct sensor coverage drops
- **Defect propagation graph + Sankey** (Origin -> Propagation -> Detection)
- **Recommendation engine** (simulation-only output)
- **What-if simulator** with before/after projected recovery
- **Leadership ROI calculator** (illustrative, formatted in INR Cr/L)
- **Deterministic seeded generation** - same seed, same data
- **SQLite persistence** (WAL mode) via a single database module
- **20+ pytest tests**, including safety tests proving no PLC writes are possible

## Personas

| Persona | What it shows |
|---|---|
| Floor Supervisor | KPI cards, 40-station live grid, root-cause banner, alerts, explainable station detail ("Why?" panel) |
| Plant Manager | Throughput, cycle-time trends by area, propagation Sankey, station matrix, bottleneck Pareto, missing-data experiment |
| Leadership | Executive KPIs, impact summary, ROI calculator with explicit disclaimer |
| What-If Simulator | Recommendations, projected recovery, PLC-write safety proof |

## Quickstart

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows   (source .venv/bin/activate on Linux/macOS)
pip install -r requirements.txt
python scripts/generate_data.py            # 7 days, ~5000 vehicles, seed 42
streamlit run app/dashboard.py             # or: python run.py
pytest -q                                  # test suite
```

### `generate_data.py` options

| Flag | Default | Description |
|---|---|---|
| `--days` | `7.0` | Days of production history to simulate |
| `--stations` | `40` | Accepted but fixed; prototype models exactly 40 stations |
| `--rate` | `46` | Arrival rate (vehicles/hour during shifts); keeps the line realistically congested |
| `--vehicles` | `2400` | Approximate vehicle count target (actual count follows `--rate`) |
| `--seed` | `42` | RNG seed (deterministic output) |
| `--scenario` | `normal` | Initial scenario baked into history |

Also see `scripts/demo_scenario.py` (one-shot judge demo: resets, injects B07 degradation, prints root-cause ranking) and `scripts/reset_database.py`.

## Scenario controls

Sidebar scenario dropdown (keys from `app/config/plant_config.py::SCENARIOS`):

| Key | Label |
|---|---|
| `normal` | Normal Production |
| `b07_mechanical` | B07 Mechanical Degradation |
| `p04_sensor_failure` | P04 Sensor Failure |
| `f12_quality_defect` | F12 Quality Defect (origin B07) |
| `material_shortage` | Material Shortage (P05 feed) |
| `high_modelc_mix` | High Model-C Mix |
| `multi_causal` | Multi-Causal Failure |

Sidebar action buttons: **Inject Failure** (re-simulates the last window under the selected scenario), **Reset Simulation** (back to normal production), **Generate New Shift** (refresh data).

## Demo script (~3-5 min)

1. Open the dashboard (`python run.py`) - Floor Supervisor view shows a mostly green 40-station grid.
2. Select **B07 Mechanical Degradation** in the sidebar and click **Inject Failure**.
3. Point at **B07**: health deteriorates even though its torque/vibration sensors are dropping out (85% dropout probability) - contextual inference fills the gap, confidence reflects low coverage.
4. Show the root-cause banner naming **B07** with its confidence score and coverage figure.
5. Switch to **Plant Manager**: defect chain **B07 -> P03 -> F10** visible in the propagation Sankey.
6. Open **What-If Simulator**, simulate maintenance on B07, show the before/after projected recovery.
7. Close on **Leadership**: impact KPIs and illustrative ROI (with disclaimer).

## Safety & boundaries

- **Simulation only.** No PLC, OPC-UA, Modbus, or any fieldbus connectivity exists.
- Zero external writes: all persistence is local SQLite (`data/digitaltwin.db`, override via `DIGITALTWIN_DB` env var).
- Every recommendation carries `simulation_only=True`.
- `PLCAdapter.write()` raises `RuntimeError` unconditionally - enforced by tests.

## Tech stack

| Component | Choice |
|---|---|
| Language | Python 3.11+ |
| UI | Streamlit |
| Data | pandas, numpy, scipy |
| ML | scikit-learn (IsolationForest auxiliary anomaly model) |
| Visualization | plotly |
| Validation | pydantic |
| Synthetic identity data | faker |
| Testing | pytest |
| Storage | SQLite (WAL) |

## Project structure

```
digitaltwin/
├── app/
│   ├── dashboard.py            # Streamlit entry point (sidebar, personas, actions)
│   ├── ui/                     # supervisor, manager, leadership, what-if views
│   ├── simulation/             # plant topology, line sim, vehicles, sensors, scenarios, injection
│   ├── analytics/              # features, inference, anomaly, bottleneck, propagation,
│   │                           #   recommendations, what-if
│   ├── data/                   # database.py (all SQL), schemas.py, seed.py
│   └── config/                 # plant_config.py (stations, models, scenarios)
├── tests/                      # pytest suite incl. missing-data + PLC-safety tests
├── scripts/
│   ├── generate_data.py        # build the demo database
│   ├── demo_scenario.py        # one-shot end-to-end judge demo
│   └── reset_database.py       # wipe/rebuild storage
├── data/
│   └── digitaltwin.db          # created on first generation (gitignored)
├── run.py                      # streamlit launcher
├── INTERFACE.md                # internal API contract for module authors
└── requirements.txt
```

See `INTERFACE.md` for the internal API contract (module imports, DB schema, inference outputs).

## Limitations

Honest scope, because this is a prototype:

- **Prototype-scale data volumes** - days of simulated history, not months of plant archives.
- **Simplified linear routing** - single-pass serial line, no rework loops or parallel branches.
- **Queue/starvation figures are DES proxies** derived from simulated waits, not MES signals.
- **ROI numbers are illustrative** - hardcoded assumptions behind the Leadership calculator.
- **Not an MES/SCADA replacement** - no historian integration, alarm management, or recipe control.
