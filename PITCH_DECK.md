# LineTwin.ai — Pitch Deck Content (Round 2)

Reference doc for building the actual slides. Every claim below is checked
against the real code/README/discussion.txt — nothing invented.

---

## Slide 1 — The Problem (in the judges' own language)

**Headline:** Real assembly lines are patchwork, not perfectly instrumented.

- Legacy + modern equipment on the same line → **uneven instrumentation is
  the norm, not the exception**. In our reference plant: 40% of stations
  richly instrumented, 35% medium, 25% nearly blind.
- Bottlenecks and defects have **multi-causal, intermittent root causes**
  (equipment wear, operator variation, upstream part quality, environment) —
  hard to isolate from data alone.
- A defect introduced early **may not surface until a much later inspection
  point** — by then, many downstream units can carry the same undetected
  issue.
- Three different stakeholders need three different views of the *same*
  line: a floor supervisor needs real-time signals, a plant manager needs
  weekly planning trends, leadership needs a rollout business case.

**Framing line for delivery:** "This is the brief's own problem, stated
plainly — we didn't design for the easy version of this."

---

## Slide 2 — The Core Idea

**One line, big on the slide:**
> A digital twin that stays useful even where sensors go dark.

**Architecture diagram** (recreate from the README):

```
Simulation Engine  →  Data Processing  →  Digital Twin Inference  →  Dashboards
   (OBSERVE)           (OBSERVE)            (INFER → RECOMMEND)      (multi-persona)

                                    CONTROL — deliberately impossible
```

Walk the four verbs: **OBSERVE** (simulate/ingest telemetry, handle missing
data) -> **INFER** (health, anomaly, bottleneck, confidence, root cause,
explainability) -> **RECOMMEND** (simulation-only suggested actions) ->
**SIMULATE** (what-if projection). **CONTROL is crossed out** — sets up
Slide 6.

---

## Slide 3 — The Actual Differentiator (spend the most time here)

**Headline:** Context-aware inference, not "no sensor = no answer."

For every station — instrumented or not — the twin estimates health,
anomaly, and bottleneck scores from five signal families:
1. Local cycle-time deviation vs. **model-aware baselines** (a Model-C
   vehicle is *expected* to run slower — the twin doesn't confuse that with
   a fault)
2. Upstream/downstream flow and **queue pressure**
3. **Starvation/blocking rates** and wait times
4. Defect rates and **manual checklist outcomes**
5. **Neighbor health** and historical behavior

**The weighting itself adapts to coverage** — as direct sensor signal drops,
the model leans harder on context. Concrete numbers to put on the slide:
at a *rich* station, ~55% of the anomaly score comes from direct sensors;
at a *sparse* station, that drops to 10% and **trend + neighbor context
carries 50%+ of the signal instead.**

**Every score ships with:**
- An explicit **confidence value**, tied to effective sensor coverage — a
  number is never presented without saying how much to trust it.
- A full **"Why?" explainability panel** — every contributing factor and its
  weight, no black box.

**Concrete proof point for the slide:** during the B07 Mechanical
Degradation scenario, B07's own torque/vibration sensors go almost
completely dark (deliberately, as part of the failure) — and the twin still
correctly names B07 as the root cause, with confidence honestly reflecting
the reduced coverage rather than pretending certainty it doesn't have.

---

## Slide 4 — Live Demo (script + screen-recording fallback)

Record a 90-second backup video — never trust conference wifi live.

1. **Land on Floor Supervisor** — mostly green 40-station grid, normal
   production.
2. **Inject "B07 Mechanical Degradation"** from the scenario selector.
3. **Point at B07**: health visibly degrades *while its own sensors drop
   out* — open its detail panel, show effective coverage collapsing while
   confidence stays meaningful and honest.
4. **Root-cause banner** names B07 explicitly, with its confidence and
   coverage numbers on screen.
5. **Switch scenario to "Multi-Causal"** — three simultaneous failures
   (B07 mechanical degradation + P04 sensor outage + a Model-C mix spike).
   The twin **still ranks B07 as the single root cause**, not a confused
   average of three symptoms. This is the single strongest "this actually
   works" moment in the whole pitch — don't rush it.
6. **Plant Manager**: propagation Sankey showing the defect chain
   B07 -> P03 -> F10.
7. **What-If Simulator**: simulate "Schedule preventive maintenance" on
   B07, show before/after projected recovery.

---

## Slide 5 — Three Personas, One Model

Side-by-side screenshots, one slide, three columns:

| Floor Supervisor | Plant Manager | Leadership |
|---|---|---|
| KPI cards, live 40-station grid, root-cause alarm banner, alerts, "Why?" panel | Throughput/cycle-time trends by area, propagation Sankey, station matrix, bottleneck Pareto, missing-data lab | Executive KPIs, impact summary, illustrative ROI calculator |
| Built for: answers in seconds, mid-shift | Built for: weekly planning decisions | Built for: investment decisions |

**Line to say out loud:** "One inference engine. Three audiences. Nobody has
to translate a data-science dashboard into a business case by hand."

---

## Slide 6 — Safety by Design

- The brief itself flags that **modifying live production systems carries
  real operational risk** — that's exactly why this twin's architecture
  makes control structurally impossible, not just policy-forbidden.
- `PLCAdapter.write()` **unconditionally raises `RuntimeError`** — enforced
  by an actual automated test (`test_safety.py`), not a comment or a
  promise.
- **On stage: literally click "Attempt PLC Write (live)."** It's a real
  backend call into the real, unmodified adapter class — it raises the
  error live, in front of the judges. This is provable, not claimed.

**Framing line:** "We're not telling you it's safe. We're about to show you
it's impossible to make it unsafe."

---

## Slide 7 — Business Case

**Phased rollout, not a big-bang pitch:**
- **Phase 1 — Shadow-mode pilot**, one line, reading *only* existing
  sensors. No new hardware spend before the twin proves itself against real
  outcomes.
- **Phase 2 — Targeted low-cost sensing**, guided by the twin's own output:
  it already identifies which stations are both *high-criticality* and
  *sensor-poor* (the exact stations worth instrumenting first) — the twin
  tells you where to spend hardware budget, instead of guessing.
- **Phase 3 — Multi-line rollout**, once scenario/inference logic is
  generalized from "this specific 40-station layout" to
  criteria-driven ("any high-criticality, sparse-coverage station of type
  X") — see Slide 8.

**ROI calculator**: explicitly labeled **illustrative**, INR Cr/L
formatting, assumptions shown rather than a bare headline number — judges
distrust unlabeled ROI claims far more than modest, honest ones.

---

## Slide 8 — Risks & Mitigations (turn self-audit into a strength)

**Framing line:** "We didn't wait for judges to find these. We audited our
own prototype and are already tracking fixes."

| Risk | Mitigation |
|---|---|
| Scenario failure definitions are currently hardwired to specific station IDs (e.g. always "B07"), not generalizable | Roadmap: make scenario targeting criteria-based (criticality + telemetry class + station type) so the same failure templates apply to any plant layout — directly answers the brief's own "Scalability & ROI" ask |
| Station criticality is tracked but doesn't yet weight urgency/alerting | Planned: criticality-weighted scoring, so a dip at a high-criticality station is surfaced above the same dip at a low-criticality one |
| Under-triage vs. over-triage tradeoff (missed defects vs. alert fatigue) | Deliberately tuned to bias toward escalation under uncertainty; human override is always the final authority, never automated action |
| Auxiliary ML anomaly signal can silently degrade exactly at the sensor-poor stations that matter most | Already identified in our own internal review; fix scoped (track per-station fitted feature set instead of assuming a fixed column layout) |

---

## Slide 9 — Honest Limitations (pulled straight from the README)

- **Prototype-scale data** — days of simulated history, not months of real
  plant archives.
- **Simplified linear routing** — single-pass serial line, no rework loops
  or parallel branches yet.
- **Queue/starvation figures are simulation proxies**, not live MES
  signals.
- **ROI numbers are illustrative** — hardcoded assumptions, stated as such.
- **Not an MES/SCADA replacement** — no historian integration, alarm
  management, or recipe control.

**Framing line:** "We scoped this honestly instead of overselling it. Here's
exactly what's simulated today versus what real plant integration would
require."

---

## Slide 10 — Close

- Restate the one-liner: *a digital twin that stays useful even where
  sensors go dark.*
- Team credits.
- Clear ask: what you want from the judges (advance to next round /
  feedback on the generalization roadmap / etc — fill in before presenting).

---

## Numbers worth having on hand for Q&A

- 40-station mixed-model plant, 4 vehicle models, 7 days simulated ~
  2,300-5,100 vehicles, 90-200K telemetry rows depending on generation run
- 21/21 automated tests passing, including the PLC-write safety proof
- Sensor coverage bands: rich 80-100%, medium 45-75%, sparse 15-35%
- Deterministic, seeded generation (seed 42) — every demo number is
  reproducible on request
