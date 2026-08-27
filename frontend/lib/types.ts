export type TelemetryClass = "rich" | "medium" | "sparse";
export type Status = "Healthy" | "Watch" | "Degraded" | "Critical";
export type Severity = "INFO" | "WARNING" | "CRITICAL";
export type MachineState =
  | "RUNNING"
  | "STARVED"
  | "BLOCKED"
  | "MAINTENANCE"
  | "CHANGEOVER";

export interface Station {
  station_id: string;
  station_name: string;
  area: string;
  station_type: string;
  sequence: number;
  cycle_time_target: number;
  cycle_time_std: number;
  sensor_coverage: number;
  telemetry_class: TelemetryClass;
  criticality: "high" | "medium" | "low";
  torque_target: number;
  torque_tol: number;
}

export interface ExplanationEntry {
  factor: string;
  detail: string;
  weight: number;
}

export interface StationMetric {
  bucket_ts: string;
  station_id: string;
  throughput_vph: number;
  avg_cycle_time: number;
  ct_deviation_pct: number;
  queue_length: number;
  queue_pressure: number;
  starvation_rate: number;
  blocking_rate: number;
  defect_rate: number;
  sensor_coverage: number;
  health_score: number;
  anomaly_score: number;
  bottleneck_score: number;
  bottleneck_prob: number;
  confidence: number;
  status: Status;
  causes: string[];
  explanation: ExplanationEntry[];
}

export interface Alert {
  alert_id: string;
  ts: string;
  station_id: string;
  severity: Severity;
  kind: string;
  message: string;
  confidence: number;
  sensor_coverage: number;
  causes: string[];
  active: number;
}

export interface Defect {
  defect_id: string;
  ts_origin: string;
  origin_station: string;
  defect_type: string;
  severity: number;
  propagation_probability: number;
  affected_stations_json: string;
  detected_station: string | null;
  ts_detected: string | null;
  scenario: string;
}

export interface SankeyEdge {
  source: string;
  target: string;
  value: number;
}

export interface Recommendation {
  rec_id: string;
  ts: string;
  station_id: string;
  issue: string;
  evidence: string[];
  recommended_action: string;
  expected_effect: string;
  confidence: number;
  simulation_only: number;
}

export interface Scenario {
  key: string;
  label: string;
  description: string;
  target_station: string | null;
  defect_chain: string[];
  window_hours: number;
  severity: number;
}

export interface Meta {
  active_scenario: string;
  sim_clock: string | null;
  seed: number;
  counts: { vehicles: number; telemetry: number };
  generated_at: string | null;
  has_data: boolean;
}

export interface TelemetryRow {
  ts: string;
  station_id: string;
  vehicle_id: string;
  vehicle_model: string;
  cycle_time: number | null;
  torque: number | null;
  vibration: number | null;
  temperature: number | null;
  motor_current: number | null;
  pressure: number | null;
  machine_state: MachineState;
  manual_checklist: number | null;
  sensor_available: number;
  data_quality: number;
  wait_sec: number;
  defective_here: number;
}

export interface WhatIfResult {
  before: {
    throughput_vph: number;
    station_cycle_time: number;
    health: number;
    bottleneck_prob: number;
  };
  after: {
    throughput_vph: number;
    station_cycle_time: number;
    projected_health: number;
    projected_bottleneck_prob: number;
    projected_sensor_coverage: number;
  };
  projected_improvement_pct: number;
  action_label: string;
  simulation_only: boolean;
  ts: string;
  logged: boolean;
}

export interface ConfidenceCurvePoint {
  coverage: number;
  confidence: number;
  detection_proxy: number;
}
