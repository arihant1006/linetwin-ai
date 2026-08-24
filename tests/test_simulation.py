"""Structural simulation tests: station registry, line graph, vehicle flow, telemetry."""
from __future__ import annotations

import re
from datetime import datetime

from app.config.plant_config import (AREA_COUNTS, AREAS, TELEMETRY_CLASS_MAP)
from app.simulation.line import LineSimulator
from app.simulation.sensors import TelemetryBuilder


def test_40_stations_exist(specs):
    assert len(specs) == 40
    counts = specs.groupby("area").size().to_dict()
    assert set(counts) == set(AREAS)
    for area in AREAS:
        assert counts[area] == AREA_COUNTS[area], (
            f"{area}: expected {AREA_COUNTS[area]}, got {counts[area]}")
    assert counts["Body Shop"] == 15
    assert counts["Paint Shop"] == 10
    assert counts["Final Assembly"] == 15


def test_sequences_valid(specs, plant):
    seq = specs["sequence"]
    assert seq.is_unique, "sequence values must be unique"
    assert sorted(seq.tolist()) == list(range(1, 41))

    along_line = specs.loc[plant.stations, "sequence"].tolist()
    assert along_line == list(range(1, 41)), \
        "sequence must strictly increase 1..40 along plant.stations order"

    assert plant.next_station("B15") == "P01"
    assert plant.next_station("P10") == "F01"
    assert plant.prev_station(plant.stations[0]) is None
    assert plant.next_station(plant.stations[-1]) is None


def test_vehicle_flow(specs):
    start = datetime(2026, 8, 18, 8, 0, 0)
    end = datetime(2026, 8, 18, 14, 0, 0)  # 6 production hours (08:00-14:00)
    run = LineSimulator(specs, seed=1).run(start, end, target_rate_vph=25)

    visits = run.visits
    assert not visits.empty, "simulator produced no station visits"
    assert len(visits) >= 40 * 100, "expected a healthy volume of visits"

    first_rows = visits.drop_duplicates(subset="vehicle_id", keep="first")
    assert (first_rows["station_id"] == "B01").all(), \
        "every vehicle must enter the line at B01"
    assert visits["vehicle_id"].str.fullmatch(r"VH-\d{6}").all(), \
        "vehicle ids must match VH-%06d"
    assert (visits["cycle_time"] > 0).all(), "cycle_time must be positive"


def test_telemetry_distributions(specs):
    start = datetime(2026, 8, 18, 8, 0, 0)
    end = datetime(2026, 8, 18, 14, 0, 0)
    run = LineSimulator(specs, seed=1).run(start, end, target_rate_vph=25)

    tel = TelemetryBuilder(specs, seed=42, outages=[]).build(run.visits, plan=None)
    assert not tel.empty, "TelemetryBuilder produced no rows"

    vib = tel["vibration"].dropna()
    assert len(vib) > 0, "vibration should be present for sensor-rich stations"
    assert 1.2 < float(vib.mean()) < 2.8, f"vibration mean out of band: {vib.mean()}"

    temp = tel["temperature"].dropna()
    assert len(temp) > 0, "temperature should be present for rich/medium stations"
    assert 45 < float(temp.mean()) < 95, f"temperature mean out of band: {temp.mean()}"

    sparse_ids = TELEMETRY_CLASS_MAP["sparse"]
    rich_ids = TELEMETRY_CLASS_MAP["rich"]

    sparse_rows = tel[tel["station_id"].isin(sparse_ids)]
    rich_rows = tel[tel["station_id"].isin(rich_ids)]
    assert not sparse_rows.empty and not rich_rows.empty
    assert sparse_rows["torque"].isna().all(), \
        "sparse-class stations must have no torque channel at all"
    assert rich_rows["manual_checklist"].isna().all(), \
        "rich-class rows must carry NULL manual_checklist"
    assert sparse_rows["manual_checklist"].notna().all(), \
        "sparse-class rows must always carry a manual_checklist value"
