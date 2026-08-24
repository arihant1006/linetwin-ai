"""Central plant configuration: stations, models, scenarios, constants."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

SEED_DEFAULT = 42

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "digitaltwin.db"

AREAS = ["Body Shop", "Paint Shop", "Final Assembly"]
AREA_PREFIX = {"Body Shop": "B", "Paint Shop": "P", "Final Assembly": "F"}
AREA_COUNTS = {"Body Shop": 15, "Paint Shop": 10, "Final Assembly": 15}

VEHICLE_MODELS = ["Model-A", "Model-B", "Model-C", "Model-D"]
MODEL_MIX = {"Model-A": 0.35, "Model-B": 0.30, "Model-C": 0.20, "Model-D": 0.15}
MODEL_CT_MULTIPLIER = {"Model-A": 1.00, "Model-B": 1.06, "Model-C": 1.18, "Model-D": 1.10}
MODEL_TORQUE_DELTA_NM = {"Model-A": 0.0, "Model-B": 2.0, "Model-C": 4.5, "Model-D": 3.0}
HIGH_MIX_MODEL = "Model-C"

TELEMETRY_CLASSES = ["rich", "medium", "sparse"]
RICH_SENSORS = ["torque", "vibration", "temperature", "motor_current", "pressure",
                "cycle_time", "machine_state"]
MEDIUM_SENSORS = ["cycle_time", "machine_state", "temperature", "production_count",
                  "manual_checklist"]
SPARSE_SENSORS = ["cycle_time", "production_count", "manual_checklist"]

TYPE_PARAMS = {
    "welding":           {"ct": 54.0, "std": 4.0, "torque": 65.0},
    "fastening":         {"ct": 48.0, "std": 3.0, "torque": 48.0},
    "torque":            {"ct": 44.0, "std": 3.0, "torque": 55.0},
    "sealing":           {"ct": 50.0, "std": 3.5, "torque": 0.0},
    "painting":          {"ct": 62.0, "std": 5.0, "torque": 0.0},
    "curing":            {"ct": 58.0, "std": 4.0, "torque": 0.0},
    "inspection":        {"ct": 36.0, "std": 3.0, "torque": 0.0},
    "vision_inspection": {"ct": 30.0, "std": 2.5, "torque": 0.0},
    "assembly":          {"ct": 66.0, "std": 6.0, "torque": 42.0},
    "electrical":        {"ct": 58.0, "std": 4.0, "torque": 38.0},
}

STATION_TYPE_MODEL_FACTOR = {
    "welding":   {"Model-A": 1.00, "Model-B": 1.05, "Model-C": 1.14, "Model-D": 1.08},
    "fastening": {"Model-A": 1.00, "Model-B": 1.07, "Model-C": 1.22, "Model-D": 1.10},
    "torque":    {"Model-A": 1.00, "Model-B": 1.06, "Model-C": 1.19, "Model-D": 1.11},
    "sealing":   {"Model-A": 1.00, "Model-B": 1.04, "Model-C": 1.12, "Model-D": 1.15},
    "painting":  {"Model-A": 1.00, "Model-B": 1.03, "Model-C": 1.10, "Model-D": 1.25},
    "curing":    {"Model-A": 1.00, "Model-B": 1.02, "Model-C": 1.08, "Model-D": 1.12},
    "inspection":{"Model-A": 1.00, "Model-B": 1.04, "Model-C": 1.13, "Model-D": 1.06},
    "vision_inspection": {"Model-A": 1.00, "Model-B": 1.03, "Model-C": 1.09, "Model-D": 1.05},
    "assembly":  {"Model-A": 1.00, "Model-B": 1.08, "Model-C": 1.26, "Model-D": 1.14},
    "electrical":{"Model-A": 1.00, "Model-B": 1.06, "Model-C": 1.21, "Model-D": 1.17},
}

STATION_DEFS = [
    ("B01", "Underbody Framing",      "Body Shop", "welding"),
    ("B02", "Side Frame Weld LH",     "Body Shop", "welding"),
    ("B03", "Side Frame Weld RH",     "Body Shop", "welding"),
    ("B04", "Roof Panel Welding",     "Body Shop", "welding"),
    ("B05", "Body-in-White Weld",     "Body Shop", "welding"),
    ("B06", "Sub-Assembly Fastening", "Body Shop", "fastening"),
    ("B07", "Chassis Fastening Cell", "Body Shop", "fastening"),
    ("B08", "Bolting Station",        "Body Shop", "torque"),
    ("B09", "Seam Sealing",           "Body Shop", "sealing"),
    ("B10", "Structural Weld Rework", "Body Shop", "welding"),
    ("B11", "Wheel Arch Torque",      "Body Shop", "torque"),
    ("B12", "Door Mount Fastening",   "Body Shop", "fastening"),
    ("B13", "Weld Vision Check",      "Body Shop", "vision_inspection"),
    ("B14", "Body Dimension Audit",   "Body Shop", "inspection"),
    ("B15", "Battery Marriage",       "Body Shop", "electrical"),
    ("P01", "Pretreatment Rinse",     "Paint Shop", "inspection"),
    ("P02", "ED Coat Application",    "Paint Shop", "painting"),
    ("P03", "Base Coat Booth 1",      "Paint Shop", "painting"),
    ("P04", "Base Coat Booth 2",      "Paint Shop", "painting"),
    ("P05", "E-Curing Oven",          "Paint Shop", "curing"),
    ("P06", "Clear Coat Booth",       "Paint Shop", "painting"),
    ("P07", "Paint Sanding Bay",      "Paint Shop", "inspection"),
    ("P08", "Cavity Wax Sealing",     "Paint Shop", "sealing"),
    ("P09", "Paint Vision Audit",     "Paint Shop", "vision_inspection"),
    ("P10", "Final Paint Cure",       "Paint Shop", "curing"),
    ("F01", "Trim Line Start",        "Final Assembly", "assembly"),
    ("F02", "Harness Routing",        "Final Assembly", "electrical"),
    ("F03", "Dashboard Assembly",     "Final Assembly", "assembly"),
    ("F04", "Headliner Fit",          "Final Assembly", "assembly"),
    ("F05", "Suspension Torque",      "Final Assembly", "torque"),
    ("F06", "Seat Installation",      "Final Assembly", "assembly"),
    ("F07", "ECU Flash & Test",       "Final Assembly", "electrical"),
    ("F08", "Fluid Fill",             "Final Assembly", "assembly"),
    ("F09", "Wheel Fastening",        "Final Assembly", "fastening"),
    ("F10", "Door Line Assembly",     "Final Assembly", "assembly"),
    ("F11", "ADAS Calibration",       "Final Assembly", "electrical"),
    ("F12", "Chassis Dynamic Torque", "Final Assembly", "torque"),
    ("F13", "Roll-Off Vision Gate",   "Final Assembly", "vision_inspection"),
    ("F14", "Interior Audit Bench",   "Final Assembly", "assembly"),
    ("F15", "End-of-Line Inspection", "Final Assembly", "inspection"),
]

TELEMETRY_CLASS_MAP = {
    "rich": ["B01", "B02", "B03", "B04", "B07", "B08", "B11",
             "P01", "P03", "P04", "P05", "P06", "F01", "F05", "F07", "F12"],
    "medium": ["B05", "B06", "B09", "B10", "B14", "P02", "P07", "P08", "P09",
               "F02", "F03", "F06", "F11", "F14"],
    "sparse": ["B12", "B13", "B15", "P10", "F04", "F08", "F09", "F10", "F13", "F15"],
}

CRITICALITY_MAP = {
    "high": ["B05", "B07", "B13", "B15", "P03", "P05", "P09", "F01", "F07", "F09", "F12", "F13"],
    "medium": ["B01", "B04", "B08", "B11", "P02", "P04", "P06", "F02", "F05", "F10", "F11", "F15"],
}
CRITICALITY_LOOKUP = {s: "high" for s in CRITICALITY_MAP["high"]}
CRITICALITY_LOOKUP.update({s: "medium" for s in CRITICALITY_MAP["medium"]})

SENSOR_COVERAGE_RANGE = {
    "rich": (0.80, 1.00),
    "medium": (0.45, 0.75),
    "sparse": (0.15, 0.35),
}

SHIFT_START_HOUR = 6
SHIFT_END_HOUR = 22
PRODUCTION_HOURS_PER_DAY = SHIFT_END_HOUR - SHIFT_START_HOUR
TARGET_RATE_VPH = 46.0

CT_TARGET_OVERRIDES = {
    "B07": 68.0,
    "B07_STD": None,
}
CT_STD_OVERRIDES = {"B07": 5.0}


@dataclass(frozen=True)
class ScenarioSpec:
    key: str
    label: str
    description: str
    target_station: str | None
    defect_chain: tuple[str, ...] = ()
    window_hours: float = 8.0
    severity: float = 1.0
    params: dict = field(default_factory=dict)


SCENARIOS: dict[str, ScenarioSpec] = {
    "normal": ScenarioSpec(
        key="normal", label="Normal Production",
        description="Healthy mixed-model production across all three areas.",
        target_station=None,
    ),
    "b07_mechanical": ScenarioSpec(
        key="b07_mechanical", label="B07 Mechanical Degradation",
        description=("Torque sensor drifts out and vibration telemetry becomes intermittent "
                     "while cycle time creeps up and queues build upstream of B07."),
        target_station="B07",
        defect_chain=("B07", "P03", "F10"),
        window_hours=8.0,
        severity=1.0,
        params=dict(ct_mult=1.30, vib_mult=2.0, temp_add=9.0, current_mult=1.18,
                    torque_bias=-0.07, sensor_dropout_p=0.85,
                    sensor_dropout_sensors=("torque", "vibration"),
                    checklist_fail_p=0.02, queue_ramp_hours=3.0,
                    defect_rate_p=0.16),
    ),
    "p04_sensor_failure": ScenarioSpec(
        key="p04_sensor_failure", label="P04 Sensor Failure",
        description="Booth 2 telemetry drops into outage windows while production continues.",
        target_station="P04",
        window_hours=8.0,
        severity=1.0,
        params=dict(sensor_dropout_p=0.92, ct_mult=1.06,
                    checklist_fail_p=0.03, defect_rate_p=0.05),
    ),
    "f12_quality_defect": ScenarioSpec(
        key="f12_quality_defect", label="F12 Quality Defect (origin B07)",
        description=("A fastening defect created at B07 escapes body inspection and is finally "
                     "detected at the F12 dynamic torque check."),
        target_station="B07",
        defect_chain=("B07", "P03", "F12"),
        window_hours=8.0,
        severity=1.0,
        params=dict(defect_rate_p=0.28, detection_station="F12"),
    ),
    "material_shortage": ScenarioSpec(
        key="material_shortage", label="Material Shortage (P05 feed)",
        description=("Sequenced-part supply to the e-coat cure area dries up; P05 starves, "
                     "upstream stations block, cycle times stay normal."),
        target_station="P05",
        window_hours=8.0,
        severity=1.0,
        params=dict(starve_station="P05", starve_gap_add=210.0,
                    block_stations=("P03", "P04"), checklist_fail_p=0.04),
    ),
    "high_modelc_mix": ScenarioSpec(
        key="high_modelc_mix", label="High Model-C Mix",
        description="Model-C share jumps to ~55%; longer assembly operations stretch cycle times plant-wide.",
        target_station=None,
        window_hours=8.0,
        severity=1.0,
        params=dict(model_mix={"Model-A": 0.18, "Model-B": 0.20,
                               "Model-C": 0.55, "Model-D": 0.07}),
    ),
    "multi_causal": ScenarioSpec(
        key="multi_causal", label="Multi-Causal Failure",
        description=("Simultaneous B07 mechanical degradation, P04 sensor outage and a Model-C mix spike - "
                     "the engine must still rank B07 as the root cause."),
        target_station="B07",
        defect_chain=("B07", "P03", "F10"),
        window_hours=8.0,
        severity=1.0,
        params=dict(
            ct_mult=1.24, vib_mult=1.8, temp_add=7.0, current_mult=1.14,
            torque_bias=-0.06, sensor_dropout_p=0.80,
            sensor_dropout_sensors=("torque", "vibration"),
            checklist_fail_p=0.03, queue_ramp_hours=3.0,
            defect_rate_p=0.12,
            secondary_sensor_station="P04", secondary_sensor_dropout_p=0.9,
            model_mix={"Model-A": 0.22, "Model-B": 0.22, "Model-C": 0.44, "Model-D": 0.12}),
    ),
}

SCENARIO_ORDER = ["normal", "b07_mechanical", "p04_sensor_failure", "f12_quality_defect",
                  "material_shortage", "high_modelc_mix", "multi_causal"]

HEALTH_BANDS = [(80, "Healthy"), (60, "Watch"), (40, "Degraded"), (0, "Critical")]
STATUS_EMOJI = {"Healthy": "🟢", "Watch": "🟡", "Degraded": "🟠", "Critical": "🔴"}


def status_band(health: float) -> str:
    if health >= 80:
        return "Healthy"
    if health >= 60:
        return "Watch"
    if health >= 40:
        return "Degraded"
    return "Critical"


def production_anchor(now: datetime | None = None) -> datetime:
    """Anchor timestamp snapped into the most recent production hour.

    Guarantees demos/tests behave identically day or night: outside shift
    hours the anchor rolls back to the last in-shift hour (+50 min) so the
    live window always contains dense production data.
    """
    from datetime import timedelta as _td
    ts = (now or datetime.now()).replace(second=0, microsecond=0)
    for _ in range(48):
        h = ts.hour + ts.minute / 60.0
        if SHIFT_START_HOUR <= h < SHIFT_END_HOUR:
            return ts.replace(minute=50) if ts.minute > 50 else \
                (ts.replace(minute=20) if ts.minute < 20 else ts)
        ts = (ts - _td(hours=1)).replace(minute=50)
    return ts.replace(minute=50)


def build_station_specs(seed: int = SEED_DEFAULT) -> pd.DataFrame:
    rng = np.random.default_rng(seed + 101)
    rows = []
    seq = 0
    for area in AREAS:
        prefix = AREA_PREFIX[area]
        for i in range(1, AREA_COUNTS[area] + 1):
            sid = f"{prefix}{i:02d}"
            _sid, name, _area, stype = next(d for d in STATION_DEFS if d[0] == sid)
            tcls = next(c for c, lst in TELEMETRY_CLASS_MAP.items() if sid in lst)
            p = TYPE_PARAMS[stype]
            lo, hi = SENSOR_COVERAGE_RANGE[tcls]
            seq += 1
            rows.append({
                "station_id": sid,
                "station_name": name,
                "area": area,
                "station_type": stype,
                "sequence": seq,
                "cycle_time_target": CT_TARGET_OVERRIDES.get(sid, p["ct"]),
                "cycle_time_std": CT_STD_OVERRIDES.get(sid, p["std"]),
                "sensor_coverage": round(float(rng.uniform(lo, hi)), 3),
                "telemetry_class": tcls,
                "criticality": CRITICALITY_LOOKUP.get(sid, "low"),
                "torque_target": p["torque"],
                "torque_tol": 3.0 if p["torque"] else 0.0,
                "model_compatibility": ",".join(VEHICLE_MODELS),
            })
    return pd.DataFrame(rows).set_index("station_id")


def scenario_by_label(label: str) -> ScenarioSpec:
    for s in SCENARIOS.values():
        if s.label == label:
            return s
    raise KeyError(label)
