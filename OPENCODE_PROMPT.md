# LineTwin.ai — Full Frontend Rebuild Brief for OpenCode

You are being handed a **working, tested Python backend** for a manufacturing digital-twin
prototype and asked to give it a real, professional, presentation-grade frontend. This
document is self-contained — you will not get additional context beyond this file and the
repository itself. Read it fully before writing code.

---

## 1. Project framing

This is **LineTwin.ai**, a prototype built for Round 2 of the Accenture Innovation Challenge
2026, problem track "DigitalTwin.ai." The audience evaluating this is a panel of judges
scoring a **working prototype + a pitch presentation**, not end users in a real factory. That
matters: every screen should read as "this team solved the hard technical problem AND can
communicate it," not as generic dashboard boilerplate.

**The core narrative hook, verbatim from the product's own README, is the thing to sell:**

> A local, simulation-only digital twin that infers station health and bottlenecks across a
> 40-station automotive assembly line — including where sensors are missing or dark.

Real assembly lines are never uniformly instrumented. In this simulated plant, roughly 40% of
stations have rich telemetry, 35% medium, 25% sparse — and a dying sensor on a degrading
machine can make that station look *healthier* than it actually is, because silence reads as
"nothing to report." The product's answer is **context-aware inference**: even at a station
with almost no direct sensors, the twin estimates health/anomaly/bottleneck risk from how that
station affects the flow around it — upstream queue build-up, downstream starvation, neighbor
station health, manual checklist outcomes — and it is explicit about how confident it is,
tying confidence directly to effective sensor coverage.

**The single most important design principle for this rebuild:** the product's differentiator
is not "we have a dashboard," it's "we can tell you *why*, and *how sure we are*, even when we
can't see directly." Every screen you build should make the confidence score and the
explainability ("Why?") panel first-class, prominent UI elements — not tooltips, not
buried in an expander. If a judge can't find "why does the twin think this" within one
glance, the rebuild has failed the brief regardless of how polished it looks.

---

## 2. Non-negotiables / guardrails

Read these before writing a single line of code. Violating any of these defeats the purpose
of this rebuild.

1. **Do not touch, reimplement, or "improve" anything under `app/simulation/`,
   `app/analytics/`, or the SQL inside `app/data/database.py`.** That code is the actual
   product — a tested, deterministic simulation + inference engine (21 passing pytest tests,
   including safety tests). Your job is a new **presentation layer** on top of it, full stop.
   If you find a genuine bug while wrapping this code (and there are a couple — see §3.5),
   surface it in your final report; do not silently fix it inside the analytics/simulation
   modules yourself.
2. **`PLCAdapter.write()` (in `app/analytics/whatif.py`) must remain the only thing that even
   *attempts* "control," and it must keep unconditionally raising `RuntimeError`.** Never
   build a real write-to-plant capability anywhere in the new stack — not in the FastAPI
   layer, not in the frontend. This is enforced by `tests/test_safety.py::test_plc_write_raises`
   and `test_no_network_imports`; do not add any networking/fieldbus dependency
   (`pymodbus`, OPC-UA client libs, etc.) to the new backend layer, ever, for any reason.
3. **Every recommendation and every ROI/impact number must stay visibly labeled as
   simulation-only / illustrative in the new UI.** The current UI does this via a
   `SIM ONLY` badge on recommendation cards, a red "⚠ SIMULATION ONLY — NO PLC WRITE" chip on
   the What-If page, and an explicit disclaimer banner under the Leadership ROI calculator
   ("Illustrative prototype estimate — simulated numbers, not real industrial claims."). Carry
   all three forward, and make sure `recommendation.simulation_only` and the ROI disclaimer are
   not just present but visually unmissable — this is a real credibility signal to judges who
   will be alert to hand-wavy ROI claims.
4. **Everything must run locally with no required external/cloud service** — no hosted DB, no
   third-party API keys, nothing that would fail on a judge's laptop with no internet. SQLite
   stays the persistence layer (`data/digitaltwin.db`, overridable via `DIGITALTWIN_DB`, exactly
   as today).
5. **Data must be live-wired to the real backend, not mocked.** Every screen renders data that
   actually came from `app/data/database.py` through the new FastAPI layer you build. No
   hardcoded/sample JSON fixtures shipped as the "real" data source (fixtures for Storybook/dev
   convenience are fine, but the shipped app must talk to the live API).
6. **Reproducibility matters.** The whole backend is seeded (`SEED_DEFAULT = 42`) so that a
   given scenario always produces the same numbers. Don't introduce any client-side randomness
   into anything presented as real twin output (animation/motion randomness in the landing page
   is fine, obviously — that's cosmetic, not data).

---

## 3. Backend architecture you're building

### 3.1 What exists today, and what changes

Today, `app/dashboard.py` + `app/ui/*.py` is a Streamlit app that calls the Python analytics
functions **in-process** and renders with Streamlit widgets + Plotly. You are replacing that
presentation layer with:

- **A new thin FastAPI service** (new directory, e.g. `server/` at repo root, or `app/api/` —
  your call, but keep it clearly separated from `app/simulation` and `app/analytics`) that
  imports the existing Python functions directly (same interpreter, same repo — no need for
  this to be a separate deployable service, it's a local dev server) and exposes them as JSON
  over HTTP.
- **A new Next.js (App Router, TypeScript) frontend** that replaces `app/dashboard.py` and
  `app/ui/*.py` entirely. The Streamlit files can stay in the repo for reference/fallback but
  are no longer the primary way to run the demo.

Do **not** rewrite `app/data/seed.py`'s pipeline (`compute_twin_artifacts`, `seed_database`,
`generate_history`) — call it from the FastAPI layer exactly as `app/dashboard.py` and
`app/simulation/inject.py` already do.

### 3.2 Exact functions to wrap, and what they return

Pull these directly — do not invent field names, use exactly what's below (drawn straight
from `INTERFACE.md` and the source, both already read in full):

**Stations** — `app.data.database.load_stations(conn)` → DataFrame indexed by `station_id`,
40 rows, columns: `station_name, area, station_type, sequence, cycle_time_target,
cycle_time_std, sensor_coverage(0-1), telemetry_class(rich|medium|sparse), criticality
(high|medium|low), torque_target, torque_tol, model_compatibility`. Suggested route:
`GET /api/stations`.

**Latest twin state (the "live snapshot")** — `db.load_latest_metrics(conn)` → one row per
station, the most recent `station_metrics` bucket. Columns: `bucket_ts, station_id,
throughput_vph, avg_cycle_time, ct_deviation_pct, queue_length, queue_pressure,
starvation_rate, blocking_rate, defect_rate, sensor_coverage, health_score, anomaly_score,
bottleneck_score, bottleneck_prob, confidence, status(Healthy|Watch|Degraded|Critical),
causes_json (JSON array, top-3 cause labels only — see §3.5 for why this is thin)`. Suggested
route: `GET /api/metrics/latest`.

**Metric history** — `db.load_metric_history(conn, hours=N)` → same columns as above, every
bucket in the trailing N hours, all stations. Suggested route:
`GET /api/metrics/history?hours=168` (used for the Plant Manager's weekly throughput chart)
and `?hours=24` (used for the by-area cycle-time trend).

**Raw telemetry for one station** — `db.load_telemetry(conn, station_ids=[sid])`, tail 200
rows in the current UI. Columns: `ts, station_id, vehicle_id, vehicle_model, cycle_time,
torque, vibration, temperature, motor_current, pressure, machine_state
(RUNNING|STARVED|BLOCKED|MAINTENANCE|CHANGEOVER), manual_checklist(1/0/null),
sensor_available(0-1), data_quality(0-1), wait_sec, defective_here(0/1)`. Suggested route:
`GET /api/stations/{station_id}/telemetry?limit=200`.

**Alerts** — `db.load_alerts(conn, active_only=True, limit=100)`. Columns: `alert_id, ts,
station_id, severity(INFO|WARNING|CRITICAL), kind, message, confidence(0-1),
sensor_coverage(0-1), causes_json, active(0/1)`. Route: `GET /api/alerts`.

**Defects / propagation** — `db.load_defects(conn, limit=200)`. Columns: `defect_id,
ts_origin, origin_station, defect_type, severity, propagation_probability,
affected_stations_json (ordered path list), detected_station, ts_detected, scenario`. Feed
these into `app.analytics.propagation.sankey_edges(chains)` (needs a list of dicts with
`affected_stations` and `detected_station` keys — see `_defect_sankey()` in
`app/ui/manager.py` for exactly how the existing UI reshapes the DB rows before calling it)
to get `[(source_station, target_station, count), ...]` edges for a Sankey diagram. Route:
`GET /api/defects` returning both the raw records and the precomputed `sankey_edges` so the
frontend doesn't need this logic duplicated in TypeScript.

**Recommendations** — `db.load_recommendations(conn, limit=100)`. Columns: `rec_id, ts,
station_id, issue, evidence_json (list of short strings), recommended_action,
expected_effect, confidence(0-1), simulation_only(always 1)`. Route:
`GET /api/recommendations`.

**What-if simulation** — `app.analytics.whatif.simulate_action(states, station_id,
action_key)`. `states` must be built the same way `app/ui/simulation.py::_states_from_metrics()`
does: a list of dicts with keys `station_id, avg_cycle_time, sensor_coverage, health_score,
bottleneck_prob`, sourced from `load_latest_metrics()` rows. `action_key` is one of
`reduce_buffer_release, increase_inspection, schedule_maintenance, recalibrate_sensors,
rebalance_work_content` (see `ACTIONS` dict in `app/analytics/whatif.py` for display labels).
Returns `{before: {throughput_vph, station_cycle_time, health, bottleneck_prob}, after:
{throughput_vph, station_cycle_time, projected_health, projected_bottleneck_prob,
projected_sensor_coverage}, projected_improvement_pct, action_label, simulation_only: true,
ts}`. Route: `POST /api/whatif/simulate` body `{station_id, action_key}`. After simulating,
the current UI also persists the run via `db.insert_simulation_run()` into a
`simulation_runs` table (fire-and-forget, wrap in try/except exactly as
`app/ui/simulation.py` does — a failure to log the run must never block showing the result to
the user).

**Scenarios** — `app.simulation.scenarios.all_scenarios()` → list of `ScenarioSpec(key, label,
description, target_station, defect_chain, window_hours, severity, params)`, in the fixed
order `SCENARIO_ORDER = [normal, b07_mechanical, p04_sensor_failure, f12_quality_defect,
material_shortage, high_modelc_mix, multi_causal]`. Route: `GET /api/scenarios`. Injection:
`app.simulation.inject.apply_scenario(scenario_key)` — re-simulates the live window under that
failure and recomputes all twin artifacts; this is a real, somewhat expensive operation (touches
the whole telemetry/vehicles/defects tables and reruns inference), so the frontend must show a
loading state, not assume it's instant. Route: `POST /api/scenarios/inject` body
`{scenario_key}`. Reset: `app.simulation.inject.reset_simulation()` → full re-seed back to
normal production (also expensive — regenerates ~7 days of history). Route:
`POST /api/scenarios/reset`.

**Metadata / sim clock** — `db.get_meta(conn, "active_scenario", "normal")`, and
`load_latest_metrics()["bucket_ts"].max()` as the "sim clock" shown in the current sidebar
(`⏱ Sim clock HH:MM:SS`). Also `db.count_table(conn, "vehicles")` and
`db.count_table(conn, "telemetry")`, used today to detect "no data yet, run
generate_data.py first." Route: `GET /api/meta`.

### 3.3 Full `StationState` fields (the richest single object in the system)

`app.analytics.inference.StationState` is a dataclass, not currently a DB table — most of it
gets flattened into `station_metrics` via `compute_twin_artifacts()` in `app/data/seed.py`,
but **`explanation` (the full "Why?" breakdown) is dropped and never persisted** — read §3.5,
this is the most important architectural thing to get right in your API design.

Full field list: `station_id, bucket_ts, health_score(0-100), anomaly_score(0-100),
bottleneck_score(0-100), bottleneck_prob(0-1), confidence(0-100), status, sensor_coverage
(0-1, effective), throughput_vph, cycle_time_deviation(pct), queue_pressure(0-1),
starvation_rate(0-1), blocking_rate(0-1), defect_rate(0-1), is_root_cause_candidate(bool),
causes(list[str], up to 3 ranked labels), explanation(list[dict], each
{factor: str, detail: str, weight: 0-1})`. `why_lines()` returns
`[f"{factor}: {detail}" for e in explanation]` — this is the literal text of the "Why?" panel.

`build_explanation()` in `app/analytics/inference.py` produces ~7 structured entries per
station every time inference runs: cycle-time deviation (mix-adjusted, with raw vs.
mix-adjusted breakdown), queue pressure, downstream starvation, upstream blocking, defect
creation rate, manual checklist, sensor z-scores (or "no direct telemetry available —
context-only inference" when there isn't any), and an "Inference mode" line stating the
station's telemetry class and effective coverage in plain language (e.g. "sparse-telemetry
station, effective coverage 28%; strong contextual evidence despite sparse telemetry."). This
is genuinely the single best piece of UI copy already in the codebase for making the product's
thesis concrete — surface it verbatim, well-formatted, not summarized.

### 3.4 Root-cause and propagation subtleties worth knowing (don't need to fix, just design around)

- `apply_root_cause()` marks **at most one** station as `is_root_cause_candidate=True` (the
  single highest-`bottleneck_prob` station, if `≥ 0.35`) and annotates other high-scoring
  stations with `"Likely symptom of upstream constraint"` when an upstream neighbor scores
  meaningfully higher. Design the root-cause UI around "one flagged root cause + zero or more
  flagged symptom stations," not a multi-root-cause list.
- The propagation Sankey (`build_chains_from_telemetry` → `propagate_defect` in
  `app/analytics/propagation.py`) does **not** trace an individual vehicle's literal recorded
  path through the plant — it independently re-simulates a statistically plausible downstream
  path given just an origin station and timestamp (its own RNG, `p_propagate=0.55`,
  `decay=0.88`). It's deterministic and physically reasonable, but if you build any UI copy
  implying "this is the exact vehicle's recorded journey," that would overstate what the data
  is. Frame Sankey copy as "propagation pattern," not "this vehicle's trace."

### 3.5 Bugs/gaps in the existing code you are wrapping around, not fixing

Report these back in your final summary rather than patching `app/analytics/` or
`app/simulation/` yourself (the guardrail in §2.1 applies) — but design your API to route
around the ones that affect what you can expose:

- **`explanation` (§3.3) is computed on every `compute_twin_artifacts()` run but never written
  to any DB table** — only `causes[:3]` survives into `station_metrics.causes_json`. This means
  the full "Why?" panel content is available live, in-memory, only at the moment inference
  runs (inside `apply_scenario`/`seed_database`/`reset_simulation`), and is gone by the next
  API request. **You need to decide and implement one of two approaches**: (a) have the
  FastAPI layer persist the full `explanation` list as JSON into `station_metrics` (add a
  column, e.g. `explanation_json`, via a small migration in `app/data/database.py`'s DDL — this
  is additive schema, not a rewrite of existing logic, and is in-scope for you to do) so it's
  queryable per station like everything else, or (b) recompute a station's explanation
  on-demand in a dedicated endpoint by re-running the relevant slice of the inference pipeline
  for that one station. **(a) is strongly preferred** — it's simpler, keeps the API fast, and
  keeps a historical record of *why* a station was flagged at a given point in time, which is
  itself a nice thing to show a judge ("here's what the twin said an hour ago vs. now").
- **The "Generate New Shift" action has no real effect in the current UI** — it's a UI-only
  flash message with no backend call behind it. Do not build a frontend button that fakes doing
  something. Either wire it to a real, cheap, meaningful backend action (there isn't an obvious
  existing one — `reset_simulation()` is the closest real "regenerate everything" action but is
  expensive and resets scenario state too), or drop the concept from your rebuild and say so in
  your final report. Don't silently keep the fake button.
- `app/simulation/sensors.py` applies an undocumented `* 1.4` amplification to a scenario's
  configured `sensor_dropout_p` before checking sensor availability — the effective dropout at
  full ramp is higher than what the scenario's stated probability would suggest (e.g. 0.85
  configured → ~100% effective). This only affects simulation internals, not anything you're
  building, but if you ever surface a scenario's "sensor dropout probability" as a stat in the
  UI (e.g. on a scenario-selector card describing `b07_mechanical`), be aware the displayed
  number and the actual behavior diverge slightly — prefer describing scenarios qualitatively
  ("torque and vibration sensors go dark") rather than quoting the raw configured probability.

---

## 4. The four persona views to rebuild

The product's core UX claim is "one underlying model, four audience-specific lenses." Each
view today lives in `app/ui/{supervisor,manager,leadership,simulation}.py`. Rebuild each with
its audience's actual job in mind — don't reskin one generic dashboard four times.

### 4.1 Floor Supervisor (`app/ui/supervisor.py` today)

**Job:** glance at the whole line in under 5 seconds, know instantly which station needs
attention right now, act.

**Current content:** a root-cause banner when the top bottleneck's probability exceeds 0.55
(station, confidence, sensor coverage, estimated throughput impact); 6 KPI cards (coverage-
weighted production rate, active bottleneck count, stations-at-risk count, open alert count,
vehicles in line, mean line health); a 40-station grid grouped by area (Body Shop / Paint Shop
/ Final Assembly), each station a clickable chip showing its health-band emoji + score, click
selects it; a station detail panel (health gauge, confidence/bottleneck-prob/coverage/CT-
deviation KPI tiles, target-vs-actual cycle time bar, ranked root-cause factors, the WHY box,
recent machine-state timeline, raw sensor channel line chart); an alerts panel.

**Design direction:** dark, high-contrast, alarm-grade clarity — this is a control-room screen,
not a report. Color should do real work: the health-band palette already defined
(`Healthy #22c55e / Watch #eab308 / Degraded #f97316 / Critical #ef4444`, matching
`STATUS_EMOJI` semantics 🟢🟡🟠🔴 in `app/config/plant_config.py`) should be the load-bearing
visual language across the whole 40-station grid, not just a badge color. The root-cause
banner is the single most important element on this screen when it's active — treat it like an
alarm strip, not a toast. The grid should communicate "most of the line is fine, here's what
isn't" at a glance — don't make every station chip equally visually loud.

### 4.2 Plant Manager (`app/ui/manager.py` today)

**Job:** weekly/daily planning — trends, where recurring problems concentrate, propagation
patterns, a controlled experiment demonstrating the sensor-coverage-vs-confidence relationship.

**Current content, in tabs:** (1) throughput trend over the last 7 days + cycle-time-by-area
trend over the last 24h; (2) defect propagation Sankey (origin → detection); (3) a full
station matrix table (health, bottleneck prob, defect rate, avg CT, coverage, confidence,
status — color-coded by health band); (4) a bottleneck Pareto (top 10 stations by
`bottleneck_prob × queue_pressure`); (5) a "missing-data experiment" — a chart of
`compute_confidence()` against synthetic coverage values (100/70/50/30/10%) next to a flat-100
"detection capability proxy" line, explicitly labeled as illustrative.

**Design direction:** clean analytical dashboard, information-dense but not noisy — this
persona wants defensible numbers and patterns over time, not real-time urgency. Tabs/sections
map reasonably well to a real product; keep them but give the propagation Sankey and the
missing-data lab visual weight, since together they're the most direct "does this actually
work" evidence in the whole product for a data-literate reviewer.

### 4.3 Leadership (`app/ui/leadership.py` today)

**Job:** an investment case in under 60 seconds, defensible enough to survive a skeptical
question, transparently labeled as illustrative where it is.

**Current content:** 4 "plant at a glance" KPIs (today's throughput, defect rate, a downtime
proxy derived from starvation minutes, an estimated annual loss combining downtime cost and
defect cost — `DOWNTIME_COST_HR=₹220,000`, `DEFECT_COST=₹14,000`, `VEHICLE_VALUE=₹850,000`,
all named constants at the top of `app/ui/leadership.py`, clearly illustrative); 3 "projected
impact" chips (fixed illustrative percentages: 32% downtime reduction, 41% defect reduction,
9% throughput increase — these are **not derived from the simulation**, they are hardcoded
assumptions, keep them clearly labeled as such, do not present them as measured); a fully
interactive ROI calculator (vehicles/day, production days/year, value/vehicle, downtime cost/
hour, defect cost, deployment cost — all editable number inputs) computing annual benefit, net
year-1, ROI%, and payback period; a closing disclaimer banner.

**Design direction:** boardroom-grade — restrained, generous whitespace, a small number of very
legible large numbers rather than a dense grid. INR formatting (`₹X.XX Cr` / `₹X.X L`, already
implemented in `_fmt_inr()`) should be preserved exactly, it's a real localization detail worth
keeping. The disclaimer must be genuinely prominent (not a small gray footnote) — a
sophisticated judge will specifically check whether a team is honest about which numbers are
measured vs. assumed, and this product already gets that right; don't regress it visually.

### 4.4 What-If Simulator (`app/ui/simulation.py` today)

**Job:** show the recommendation engine's output, let the user pick a station + a candidate
action and see a projected before/after, and make the "we cannot and will not write to a real
PLC" boundary undeniable.

**Current content:** recommendation cards (station badge, "SIM ONLY" badge, confidence badge,
issue, recommended action, expected effect, evidence bullets) sourced from
`recommend_all()`/persisted `recommendations`; a station + action selector and a "Simulate
Recommendation" button calling `simulate_action()`, rendering a clear BEFORE / → / AFTER
(projected) comparison across throughput, health, bottleneck probability; an "Integration
boundary" section showing the literal Python snippet that raises `RuntimeError` on any write
attempt, plus a live "Attempt PLC Write" button that actually calls `PLCAdapter().write("test")`
and displays the resulting `RuntimeError` on screen.

**Design direction:** the before/after comparison is the payload — make it visually
unambiguous which side is "now" and which is "if we did this," with a clear directional
indicator (the current ▲/▼ + color convention is fine to keep). The "Attempt PLC Write" button
that live-triggers a real `RuntimeError` from the real, unmodified `PLCAdapter` class is a
strong, concrete safety proof — keep this as an actual live backend call through your new API,
not a canned/mocked "we promise this would fail" message. It's more convincing precisely
because it's real.

---

## 5. Design system

Build a coherent token-based design system, not per-page ad hoc styling. Ground every choice
in vocabulary the product already uses about itself:

- **Health bands** — 4 states, consistent color + icon everywhere they appear (grid chips,
  KPI deltas, alert severities, the station matrix, gauge steps):
  `Healthy(#22c55e/🟢) · Watch(#eab308/🟡) · Degraded(#f97316/🟠) · Critical(#ef4444/🔴)`.
- **Machine states** (for the raw telemetry strip): `RUNNING(#22c55e) STARVED(#eab308)
  BLOCKED(#f97316) MAINTENANCE(#94a3b8) CHANGEOVER(#38bdf8)` — reuse the existing mapping in
  `STATE_COLORS` (`app/ui/components.py`).
  - **Confidence and sensor coverage** deserve their own consistent visual treatment across
  every screen they appear (which is most of them) — e.g. a small radial/ring indicator or a
  segmented bar, distinct from the health-band color language, so a viewer learns to read
  "how sure is the twin" as a separate visual channel from "how healthy is the station." This
  is the product's actual differentiator; do not let it collapse into a generic percentage
  label.
- **Typography** — the current UI uses a monospace font for numeric KPI values
  (`ui-monospace, SFMono-Regular, Menlo, monospace`) with tabular-nums, which is a good,
  deliberate choice for a control-room feel where numbers need to be scannable and stable width
  — keep that convention for all KPI/metric numerals; use a clean sans-serif for body copy and
  headings.
- **Dark base palette to start from** (from the current `CSS` block in `app/dashboard.py`, feel
  free to refine but keep the spirit — dark, desaturated background, cyan accent):
  `--bg:#0e1117 --card:#171d26 --line:#232c3b --accent:#22d3ee --txt:#e8edf4 --mut:#8b98ab`.
  The landing/story page (§6) can break from this if the narrative calls for it, but the
  operational dashboards (§4) should stay visually continuous with this control-room identity.

---

## 6. The 3D scroll centerpiece (landing/story page only)

Build a scroll-driven narrative landing page at `/` using the architecture the README already
lays out:

```
Simulation Engine  -->  Data Processing  -->  Digital Twin Inference  -->  Dashboards
(vehicles, sensors,     (validation,          (health, anomaly,           (multi-persona
 failure injection,      features,             bottleneck, confidence,     Streamlit UI
 defect propagation)     baselines,            root cause,                 -> your new
                         missing-data           explainability)             frontend)
                         handling)

Layering: OBSERVE -> INFER -> RECOMMEND -> SIMULATE
CONTROL is deliberately impossible: PLCAdapter.write() raises RuntimeError by design.
```

Turn this into a scroll-driven 3D/motion sequence — one scene/stage per pipeline layer, camera
or composition advancing as the user scrolls, each stage's copy explicitly tying back to a
real complexity from the judges' brief so the story reads as directly answering it, not as
generic hackathon flash:

- **OBSERVE** — visualize the 40-station line with uneven instrumentation (some stations lit
  up richly, some barely visible) — this is the single clearest visual metaphor available and
  should be the hero moment of the whole sequence. Copy: sensor coverage varies station to
  station; a dying sensor can make a degrading machine look healthier, not worse.
- **INFER** — visualize context flowing between neighboring stations (queue pressure from
  upstream, starvation signal from downstream) converging into a confidence-scored health
  estimate even at a dark station. Copy: multi-causal, intermittent root causes rarely show up
  as one clean signal; the twin fuses several imperfect signals and says how sure it is.
  Copy: defects introduced early can surface stations later — root-cause tracing has to look
  backward through time and through the line, not just at the current reading.
- **RECOMMEND** — visualize the ranked root-cause + evidence chain distilling into a concrete,
  human-readable action with a confidence score attached. Copy: three very different
  audiences (a floor supervisor mid-shift, a plant manager planning next week, leadership
  weighing an investment) need three different views of the same underlying model — not three
  separate products.
- **SIMULATE** — visualize a before/after projection, then an explicit dead-end where "write to
  plant" would be — literally show `PLCAdapter.write()` raising, as a design choice, not a
  limitation. Copy: this is a decision-support tool, not a control system, by design.

**Scope this precisely:** this flashy sequence lives at `/` only, as the entry point/story. The
moment a viewer clicks into the actual dashboards (`/dashboard/...`), everything should be
fast, dense, and functional — no scroll-jacking, no heavy WebGL scenes competing with real data
for frame budget. Treat §6 as the trailer and §4 as the film.

---

## 7. Tech stack

- **Frontend:** Next.js 14+ (App Router, TypeScript, strict mode).
- **Styling:** Tailwind CSS + shadcn/ui for base primitives (cards, dialogs, tabs, selects,
  tooltips) — don't hand-roll what shadcn already solves well.
- **Motion (dashboards):** Framer Motion for state transitions, hover/press feedback, panel
  reveals — kept light, kept fast.
- **3D scroll (landing only):** **React Three Fiber + drei**, driven by scroll position (e.g.
  via `@react-three/drei`'s `ScrollControls`, or GSAP `ScrollTrigger` purely for the
  scroll-position → animation-progress mapping while R3F owns the actual 3D rendering). Prefer
  R3F over a GSAP-only DOM/SVG approach because the natural visual metaphor here (a 3D line of
  40 stations, camera moving through a pipeline) genuinely benefits from real 3D depth and
  camera movement rather than 2D panel transitions — this isn't animation for its own sake,
  it's the clearest way to show "uneven instrumentation across a physical line." If you judge
  mid-build that R3F is adding more complexity than payoff for a given scene, GSAP
  ScrollTrigger over styled DOM/SVG is an acceptable fallback for that scene specifically —
  make that call scene-by-scene, and note where you diverged from R3F in your final report.
- **Charts (dashboards):** pick one of Recharts / visx / nivo for line/bar/Pareto charts
  (Recharts is the lowest-friction choice for a deadline; visx if you want more control over
  the Sankey specifically). You need at minimum: line charts (throughput trend, cycle-time-by-
  area trend, sensor-coverage-vs-confidence lab), a horizontal bar/Pareto chart, and a Sankey
  diagram (origin → detection defect propagation) — Sankey support varies by library, verify
  before committing to one.
- **Data fetching:** TanStack Query (React Query) against the FastAPI layer — use it for
  caching + polling (the Floor Supervisor view benefits from a short auto-refresh interval,
  matching the existing Streamlit "Live refresh" / speed concept — see §8 for suggested
  `SPEEDS`/interval values to reuse).
- **Client state:** Zustand (or plain React context if you prefer) for: selected persona view,
  selected scenario, selected station (shared between the grid and the detail panel, same as
  `st.session_state["selected_station"]` today), live-refresh on/off + speed.
- **Backend:** FastAPI + Pydantic (reuse the existing Pydantic models in `app/data/schemas.py`
  as your response-shape starting point where they line up — e.g. `AlertRecord`,
  `RecommendationRecord` — extend/wrap rather than redefine from scratch where the shapes
  already match) + Uvicorn. CORS enabled for local dev (`http://localhost:3000` origin).

---

## 8. Suggested route/page structure and component inventory

**Pages:**
- `/` — landing/story (§6)
- `/dashboard/supervisor` — Floor Supervisor (§4.1)
- `/dashboard/manager` — Plant Manager (§4.2)
- `/dashboard/leadership` — Leadership (§4.3)
- `/dashboard/whatif` — What-If Simulator (§4.4)
- A persistent shell around all four dashboard routes: scenario selector, persona nav, sim
  clock display, live-refresh toggle + speed (`1x/5x/10x/50x`, mapping to refresh intervals —
  the current Streamlit values are `{"5x": 4000ms, "10x": 2500ms, "50x": 1200ms}`, 1x = no
  auto-refresh), and the three scenario action buttons (Inject Failure / Reset Simulation /
  the "Generate New Shift" button per the §3.5 note — resolve what it actually does before
  shipping it).

**Shared components** (named after what's already in `app/ui/components.py` and the persona
files — keep naming continuity so the mapping from old to new is obvious):
- `StationGrid` — the 40-station chip grid, grouped by area, clickable, health-band colored.
- `StationDetailPanel` — health gauge, KPI tiles, target-vs-actual cycle time bar, ranked
  causes, and the **`WhyPanel`** (the full explanation breakdown per §3.3/§3.5 — build this as
  its own component, it's the product's differentiator, don't inline it as an afterthought).
- `ConfidenceIndicator` — the dedicated confidence/coverage visual treatment from §5.
- `HealthBadge` — the 4-band chip/pill used across grid, matrix, alerts.
- `AlertBanner` / `AlertsPanel` — root-cause banner (supervisor) and the alert list.
- `RecommendationCard` — issue/action/effect/evidence/confidence/SIM-ONLY badge.
- `WhatIfComparison` — before/→/after (projected) block.
- `ScenarioSelector` — dropdown + inject/reset actions, with the loading-state handling from
  §3.2's note that scenario injection is a real, non-instant backend operation.
- `PropagationSankey`, `ThroughputTrendChart`, `CycleTimeByAreaChart`, `BottleneckPareto`,
  `StationMatrix`, `MissingDataLab` — Plant Manager visualizations.
- `ROICalculator` — with the illustrative-disclaimer treatment from §4.3 built in, not bolted
  on.
- `PlcSafetyProof` — the "Integration boundary" snippet + live "Attempt PLC Write" button.

---

## 9. Suggested build order

Don't try to build everything simultaneously. Sequence:

1. **Stand up the FastAPI layer first**, against the existing seeded database (run
   `python scripts/generate_data.py` if `data/digitaltwin.db` doesn't exist yet). Verify every
   route in §3.2 with `curl`/httpie before writing any frontend code. Resolve the `explanation`
   persistence decision (§3.5) at this stage, since it's a schema change and easiest to do
   before other things depend on the shape.
2. **Scaffold the Next.js app + design system/tokens** (§5) — get the dark control-room base
   theme, typography, and the health-band/confidence visual language working on a bare
   component-showcase page before wiring real data.
3. **Build the four operational dashboards (§4) against live API data first** — this is the
   working-prototype requirement for Round 2 and should exist and function end-to-end (scenario
   injection included) before any time goes into the landing page. A working, plain-styled
   dashboard beats a beautiful landing page in front of a broken one.
4. **Build the 3D landing/story section last** (§6), as the polish layer, once the operational
   product is real and demoable.

---

## 10. Definition of done

Before considering this finished, verify:

- [ ] All four persona dashboards render real data from the live SQLite DB through the new
      FastAPI layer — no mocked/hardcoded data shipped in the final build.
- [ ] Scenario injection (`Inject Failure`), reset (`Reset Simulation`), and whatever you
      decided to do about "Generate New Shift" (§3.5) all work end-to-end through the new
      stack, with visible loading states (these are real, non-instant backend operations).
- [ ] The What-If Simulator's "Attempt PLC Write" button makes a real backend call that hits
      the actual unmodified `PLCAdapter.write()` and displays the real resulting
      `RuntimeError` — not a mocked/canned message.
- [ ] `simulation_only` / illustrative labeling is visually prominent everywhere
      recommendations or ROI figures appear (§2.3).
- [ ] The "Why?" explanation panel is real, full-fidelity data (§3.3/§3.5's persistence
      decision implemented), not the old UI's simplified reconstruction from raw metric
      columns.
- [ ] Health-band and confidence/coverage visual language is consistent across every screen
      it appears on (§5).
- [ ] The landing page's 3D scroll sequence is scoped to `/` only and does not degrade
      performance or interactivity on the dashboard routes.
- [ ] Responsive down to a reasonable laptop/projector resolution (judges will likely view this
      projected, not on a phone — prioritize a wide-screen presentation layout over mobile-first,
      but don't break outright on a narrower window).
- [ ] No console errors/warnings in a full click-through of all four dashboards + the landing
      page + at least one full scenario-injection cycle.
- [ ] `pytest -q` in the repo root still passes (you should not have touched anything that
      could break it, but verify — the safety tests in particular are load-bearing for the
      pitch's credibility).
- [ ] A short README addition (or a new `FRONTEND.md`) explaining how to run the new stack
      locally: start the FastAPI server, start the Next.js dev server, and confirm both against
      each other — this needs to be reproducible by someone else on the team on demo day.

---

## Final note

This backend earned its complexity — read `app/analytics/inference.py`'s docstring on the
two-pass contextual inference approach before you build the health-gauge component; the
product's actual claim ("a sensor-poor station with strong contextual agreement earns HIGH
confidence — the core prototype claim," verbatim from `app/analytics/health.py`) needs to be
visible and legible in the UI, not just true in the backend. If the frontend doesn't make that
claim obvious to a judge within the first 30 seconds of looking at a degraded, sensor-poor
station's detail panel, the rebuild hasn't done its job — the demo script in the README
(`B07 Mechanical Degradation` scenario, confidence still meaningful despite 85% sensor
dropout) is the single scene this whole rebuild needs to make land visually.
