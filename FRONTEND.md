# LineTwin.ai — Frontend & API (new stack)

The Streamlit app (`app/dashboard.py` + `app/ui/`) still runs, but the primary
demo path is now a **FastAPI service + Next.js frontend**. Both run fully
locally against the same seeded SQLite database — no external services.

## Prerequisites

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cd frontend && npm install       # Node 18+ required
```

## Run it (two terminals, from the repo root)

**1. Generate data once** (skip if `data/digitaltwin.db` already exists):

```bash
.venv/bin/python scripts/generate_data.py     # Windows: .venv\Scripts\python scripts\generate_data.py
```

**2. Start the API server** (port 8000):

```bash
.venv/bin/uvicorn server.main:app --port 8000
```

**3. Start the Next.js dev server** (port 3000):

```bash
cd frontend && npm run dev
```

Open **http://localhost:3000**

- `/` — scroll-driven 3D story page (OBSERVE → INFER → RECOMMEND → SIMULATE)
- `/dashboard/supervisor` — Floor Supervisor (live grid, root-cause alarm strip, Why? panel)
- `/dashboard/manager` — Plant Manager (trends, propagation Sankey, matrix, Pareto, missing-data lab)
- `/dashboard/leadership` — Leadership (KPIs, illustrative ROI calculator)
- `/dashboard/whatif` — What-If Simulator (recommendations, before/after projection, live PLC-write safety proof)

## Verify the two halves talk to each other

```bash
curl -s localhost:8000/api/meta          # should return active_scenario, sim_clock, counts
curl -s -o /dev/null -w "%{http_code}" localhost:3000   # 200
```

If the dashboard shows "API unreachable", the FastAPI process on port 8000 is
not running.

## Demo script (judge flow)

1. **Land on `/`**, scroll through the four layers of the story.
2. **Floor Supervisor**: note the healthy line; click a station → the full
   "Why?" explanation panel with per-factor weights and inference mode.
3. In the top bar, select **B07 Mechanical Degradation → Inject Failure**
   (takes a few seconds; a loading overlay shows while the twin re-simulates).
   The grid turns orange around B07; the alarm strip names B07 as predicted
   bottleneck even though its sensors are going dark — open B07's detail panel:
   effective sensor coverage collapses while contextual confidence stays
   meaningful, with the full explanation.
4. Try **Multi-Causal** — three simultaneous failures; the twin still ranks B07
   as the single root cause and marks downstream stations as symptoms.
5. **Plant Manager**: propagation Sankey, bottleneck Pareto, missing-data lab.
6. **What-If**: simulate *Schedule preventive maintenance* on B07 → before /
   after projection. Then hit **Attempt PLC Write** — a real backend call into
   the unmodified `PLCAdapter`, which raises `RuntimeError` live.
7. **Reset Simulation** returns everything to the seeded normal state
   (regenerates ~7 days of history; takes tens of seconds).

## Configuration

| Env var | Default | Purpose |
|---|---|---|
| `DIGITALTWIN_DB` | `data/digitaltwin.db` | SQLite location (shared by API + scripts) |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | API base for the frontend build |

## Architecture notes

- `server/main.py` is a thin read-mostly wrapper over `app.data.database`,
  `app.analytics.whatif`, and `app.simulation.inject`. It adds no inference
  logic and contains no plant-write capability anywhere.
- The full inference `explanation` list (the "Why?" content) is persisted per
  scored bucket in `station_metrics.explanation_json` (additive schema change;
  applied automatically by `ensure_schema()` on existing DB files).
- Scenario inject/reset are real, non-instant backend operations — the UI shows
  blocking overlays while they run.
- The old Streamlit UI is untouched and remains available via
  `streamlit run app/dashboard.py`.

## Known divergences from the previous UI

- **"Generate New Shift" was removed.** In the Streamlit app the button was
  cosmetic only (no backend call). Rather than ship a fake action, the new UI
  offers exactly the actions that exist: Inject Failure and Reset Simulation.
