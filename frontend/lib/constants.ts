import type { Status } from "./types";

/** Health-band palette — the load-bearing visual language of the product. */
export const STATUS_COLORS: Record<Status, string> = {
  Healthy: "#22c55e",
  Watch: "#eab308",
  Degraded: "#f97316",
  Critical: "#ef4444",
};

export const STATUS_ORDER: Status[] = [
  "Healthy",
  "Watch",
  "Degraded",
  "Critical",
];

export function statusBand(health: number): Status {
  if (health >= 80) return "Healthy";
  if (health >= 60) return "Watch";
  if (health >= 40) return "Degraded";
  return "Critical";
}

export const STATE_COLORS: Record<string, string> = {
  RUNNING: "#22c55e",
  STARVED: "#eab308",
  BLOCKED: "#f97316",
  MAINTENANCE: "#94a3b8",
  CHANGEOVER: "#38bdf8",
};

export const AREAS = ["Body Shop", "Paint Shop", "Final Assembly"] as const;

export const ACTIONS: Record<string, string> = {
  reduce_buffer_release: "Reduce conveyor buffer release threshold",
  increase_inspection: "Increase inspection sampling",
  schedule_maintenance: "Schedule preventive maintenance",
  recalibrate_sensors: "Recalibrate / reconnect sensors",
  rebalance_work_content: "Rebalance work content across stations",
};

/** Refresh speed multiplier -> poll interval ms (1x = no auto-refresh). */
export const SPEEDS: Record<string, number | false> = {
  "1x": false,
  "5x": 4000,
  "10x": 2500,
  "50x": 1200,
};

/** Illustrative constants for the Leadership ROI model (NOT measured values). */
export const DOWNTIME_COST_HR = 220_000;
export const DEFECT_COST = 14_000;
export const VEHICLE_VALUE = 850_000;

export function fmtInr(v: number): string {
  if (!Number.isFinite(v)) return "—";
  if (Math.abs(v) >= 1e7) return `₹${(v / 1e7).toFixed(2)} Cr`;
  if (Math.abs(v) >= 1e5) return `₹${(v / 1e5).toFixed(1)} L`;
  return `₹${Math.round(v).toLocaleString("en-IN")}`;
}
