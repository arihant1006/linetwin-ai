# DigitalTwin.ai - INTERNAL API CONTRACT (for module authors)

All code below already exists and WORKS. Import exactly as shown. Do not redefine.
DB path override env var: `DIGITALTWIN_DB`. Default: `<repo>/data/digitaltwin.db`.
Python: run with `.venv/bin/python` / `.venv/bin/streamlit` inside repo root `/mnt/d/Documents/GitHub/digitaltwin`.

## Config - `app/config/plant_config.py`
```python
from app.config.plant_config import (
    SCENARIOS, SCENARIO_ORDER, ScenarioSpec, VEHICLE_MODELS, AREAS,
    STATUS_EMOJI, HEALTH_BANDS, status_band, build_station_specs, scenario_by_label,
    SEED_DEFAULT)
# SCENARIOS: dict key->ScenarioSpec(key,label,description,target_station,defect_chain,window_hours,severity,params)
# status_band(health_float) -> "Healthy"|"Watch"|"Degraded"|"Critical"
# build_station_specs(seed=42) -> DataFrame indexed by station_id (40 rows), columns:
#   station_name, area, station_type, sequence, cycle_time_target, cycle_time_std,
#   sensor_coverage(0-1), telemetry_class(rich|medium|sparse), criticality,
#   torque_target, torque_tol, model_compatibility("Model-A,...")
```

## Database - `app/data/database.py` (ALL SQL lives here)
```python
from app.data import database as db
conn = db.get_conn()            # sqlite3 conn (WAL)
df = db.load_stations(conn)     # stations df indexed by station_id
tel = db.load_telemetry(conn, start=None, end=None, station_ids=None)  # full telemetry df
veh = db.load_vehicles(conn)    # vehicles df
met  = db.load_latest_metrics(conn)   # latest bucket row PER STATION (twin state snapshot), cols below
hist = db.load_metric_history(conn, hours=None)  # station_metrics history (all or last N hours)
alerts = db.load_alerts(conn, active_only=True, limit=100)      # newest first
defs  = db.load_defects(conn, limit=200)        # defect chains
recs  = db.load_recommendations(conn, limit=100)
meta_val = db.get_meta(conn, "active_scenario", default="normal")
db.count_table(conn, "telemetry") -> int
```
station_metrics columns: bucket_ts, station_id, throughput_vph, avg_cycle_time,
ct_deviation_pct, queue_length(min), queue_pressure(0-1), starvation_rate, blocking_rate,
defect_rate, sensor_coverage(observed 0-1), health_score(0-100), anomaly_score(0-100),
bottleneck_score(0-100), bottleneck_prob(0-1), confidence(0-100), status(band str),
causes_json(JSON list[str]).
telemetry columns: ts("YYYY-MM-DD HH:MM:SS"), station_id, vehicle_id, vehicle_model,
cycle_time, torque, vibration, temperature, motor_current, pressure, machine_state
(RUNNING|STARVED|BLOCKED|MAINTENANCE|CHANGEOVER), manual_checklist(1 pass/0 fail/NULL),
sensor_available(0-1), data_quality(0-1), wait_sec, defective_here(0/1).
alerts columns: alert_id, ts, station_id, severity(INFO/WARNING/CRITICAL), kind, message,
confidence(0-1), sensor_coverage(0-1), causes_json, active(0/1).
defects columns: defect_id, ts_origin, origin_station, defect_type, severity,
propagation_probability, affected_stations_json(JSON list path origin->...), detected_station,
ts_detected, scenario.
recommendations columns: rec_id, ts, station_id, issue, evidence_json(list),
recommended_action, expected_effect, confidence, simulation_only(1).

## Seeding / scenario injection - high level ops
```python
from app.data.seed import seed_database          # full reset+generate+infer
res = seed_database(days=7, vehicles_target=2400, seed=42, scenario="normal")
# res: {"ok":bool,"states":[StationState...],"alerts":[dict],"defects":[dict],
#       "recommendations":[dict],"stations":40,"telemetry_rows":int,"vehicles":int}
from app.simulation.inject import apply_scenario, reset_simulation
res = apply_scenario(scenario_key="b07_mechanical")  # re-sims last window w/ failure
res2 = reset_simulation()                            # back to normal production
```

## Inference output - `app/analytics/inference.StationState` (dataclass)
fields: station_id, bucket_ts, health_score(0-100 float), anomaly_score, bottleneck_score,
bottleneck_prob(0-1), confidence(0-100), status, sensor_coverage(0-1 effective),
throughput_vph, cycle_time_deviation(pct vs target), queue_pressure(0-1),
starvation_rate(0-1), blocking_rate(0-1), defect_rate(0-1), is_root_cause_candidate(bool),
causes(list[str]), explanation(list[dict factor,detail,weight]).
`s.why_lines()` -> list[str] explainability bullets.

## Analytics extras
```python
from app.analytics.propagation import sankey_edges        # [(src,dst,count),...] from chains list-of-dicts
from app.analytics.recommendations import recommend_all, recommend
recs = recommend_all(states, top_n=8)                     # same dicts as DB rows
from app.analytics.whatif import simulate_action, ACTIONS, PLCAdapter
out = simulate_action(states_as_dicts, "B07", "schedule_maintenance")
# states_as_dicts: list of dicts with keys station_id, avg_cycle_time, sensor_coverage,
#                  health_score, bottleneck_prob  (build from load_latest_metrics rows!)
# out: {"before":{"throughput_vph","station_cycle_time","health","bottleneck_prob"},
#       "after":{...projected_health, projected_bottleneck_prob,...},
#       "projected_improvement_pct":float,"action_label":str,"simulation_only":True}
PLCAdapter().write(x)  # ALWAYS raises RuntimeError - safety test relies on this
```

## Simulation internals (tests may use)
```python
from app.simulation.plant import PlantModel
plant = PlantModel(specs_df)           # .stations ordered B01..F15; next/prev/upstream/downstream_chain, neighbors(k=2)
from app.simulation.line import LineSimulator
run = LineSimulator(specs_df, seed=42).run(start_dt, end_dt, target_rate_vph=21.0, plan=None, vehicle_offset=0)
run.visits  # DataFrame vehicle_id,vehicle_model,station_id,ts,cycle_time,gap_sec,machine_state,blocked,defective_here,maintenance
run.vehicles
from app.simulation.scenarios import get_scenario, build_plan, all_scenarios
plan = build_plan(get_scenario("b07_mechanical"), anchor_end_dt, seed=42)  # InjectionPlan(.profiles dict sid->DegradeProfile,.outage_windows,.model_mix_override)
from app.simulation.sensors import TelemetryBuilder
tb = TelemetryBuilder(specs_df, seed=42, outages=[]); tel = tb.build(run.visits, plan)
from app.analytics.features import compute_features, BaselineStore
feat, baseline = compute_features(tel, specs_df, plant)  # MultiIndex (bucket_ts, station_id)
from app.analytics.inference import TwinInference
engine = TwinInference(specs_df, plant); engine.fit(feat_hist_part); states = engine.update(feat)
```

## Notes
- All RNG seeded => deterministic given same seed.
- Scenario window = last `window_hours` (8h default) before anchor_end (max telemetry ts).
- Sparse stations (e.g., F10, F13, B13) intentionally have almost no direct sensors;
  their state must come from contextual inference (queue/starvation/upstream CT/manual checks).
