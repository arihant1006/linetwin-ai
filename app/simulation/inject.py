"""Scenario injection: re-simulate the live window with a failure plan active."""
from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from app.config.plant_config import SEED_DEFAULT, build_station_specs
from app.data import database as db
from app.data.seed import compute_twin_artifacts, generate_history
from app.simulation.scenarios import build_plan, get_scenario


def apply_scenario(db_path=None, scenario_key: str = "b07_mechanical",
                   seed: int | None = None) -> dict:
    conn = db.get_conn(db_path)
    specs_df = db.load_stations(conn)
    if specs_df.empty:
        conn.close()
        return {"ok": False, "reason": "database not seeded - run scripts/generate_data.py"}
    from app.simulation.plant import PlantModel
    plant = PlantModel(specs_df)

    seed_val = int(seed if seed is not None else db.get_meta(conn, "seed", SEED_DEFAULT))
    anchor_row = conn.execute("SELECT MAX(ts) FROM telemetry").fetchone()[0]
    if not anchor_row:
        conn.close()
        return {"ok": False, "reason": "no telemetry"}
    anchor = pd.Timestamp(anchor_row).to_pydatetime()

    scen = get_scenario(scenario_key)
    plan = build_plan(scen, anchor, seed_val) if scenario_key != "normal" else None
    window_h = scen.window_hours if scenario_key != "normal" else 0.0
    window_start = anchor - timedelta(hours=window_h)

    conn.execute("DELETE FROM telemetry WHERE ts >= ?", (str(window_start),))
    conn.execute("DELETE FROM vehicles WHERE entry_ts >= ?", (str(window_start),))
    conn.execute("DELETE FROM defects")
    conn.commit()

    counter = int(db.get_meta(conn, "vehicles_counter", 0) or 0)
    rate = float(db.get_meta(conn, "rate_vph", 54.0) or 54.0)

    visits, tel, veh = generate_history(plant.specs, window_start, anchor, rate,
                                        seed_val + 991, plan=plan,
                                        vehicle_offset=counter)
    db.insert_telemetry(conn, tel)
    db.insert_vehicles(conn, veh)
    db.set_meta(conn, "vehicles_counter", counter + len(veh))
    db.set_meta(conn, "active_scenario", scenario_key)

    result = compute_twin_artifacts(conn)
    conn.close()
    result.update({"scenario": scenario_key, "window_hours": window_h,
                   "telemetry_rows_added": len(tel), "vehicles_added": len(veh)})
    return result


def reset_simulation(db_path=None, days: float = 7, vehicles_target: int = 2400,
                     seed: int = SEED_DEFAULT, rate_vph: float | None = None) -> dict:
    from app.data.seed import seed_database
    return seed_database(days=days, vehicles_target=vehicles_target,
                         seed=seed, db_path=db_path, scenario="normal",
                         rate_vph=rate_vph)
