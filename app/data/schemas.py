"""Pydantic schemas for records moving through the pipeline."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class StationDef(BaseModel):
    station_id: str
    station_name: str
    area: str
    station_type: str
    sequence: int
    cycle_time_target: float = Field(gt=0)
    cycle_time_std: float = Field(ge=0)
    sensor_coverage: float = Field(ge=0, le=1)
    telemetry_class: str
    criticality: str
    torque_target: float = Field(ge=0)
    torque_tol: float = Field(ge=0)
    model_compatibility: str


class VehicleRecord(BaseModel):
    vehicle_id: str
    model: str
    entry_ts: str
    exit_ts: str
    current_station: str
    quality_status: str
    defect_flags: str = "[]"

    @field_validator("quality_status")
    @classmethod
    def _status(cls, v: str) -> str:
        if v not in {"OK", "SUSPECT", "DEFECT"}:
            raise ValueError(f"bad quality_status {v}")
        return v


class TelemetryRecord(BaseModel):
    ts: str
    station_id: str
    vehicle_id: str
    vehicle_model: str
    cycle_time: float | None = None
    torque: float | None = None
    vibration: float | None = None
    temperature: float | None = None
    motor_current: float | None = None
    pressure: float | None = None
    machine_state: str
    manual_checklist: int | None = None
    sensor_available: float = Field(ge=0, le=1)
    data_quality: float = Field(ge=0, le=1)
    wait_sec: float = Field(ge=0)
    defective_here: int = 0


class AlertRecord(BaseModel):
    alert_id: str
    ts: str
    station_id: str
    severity: str
    kind: str
    message: str
    confidence: float = Field(ge=0, le=1)
    sensor_coverage: float = Field(ge=0, le=1)
    causes_json: str = "[]"
    active: int = 1


class DefectRecord(BaseModel):
    defect_id: str
    ts_origin: str
    origin_station: str
    defect_type: str
    severity: float = Field(ge=0, le=1)
    propagation_probability: float = Field(ge=0, le=1)
    affected_stations_json: str
    detected_station: str | None
    ts_detected: str | None
    scenario: str


class RecommendationRecord(BaseModel):
    rec_id: str
    ts: str
    station_id: str
    issue: str
    evidence_json: str
    recommended_action: str
    expected_effect: str
    confidence: float = Field(ge=0, le=1)
    simulation_only: int = 1


class SimulationRunRecord(BaseModel):
    run_id: str
    ts: str
    station_id: str
    action: str
    before_json: str
    after_json: str
    projected_improvement_pct: float
    note: str
