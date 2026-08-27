import type {
  Alert,
  ConfidenceCurvePoint,
  Defect,
  Meta,
  Recommendation,
  SankeyEdge,
  Scenario,
  Station,
  StationMetric,
  TelemetryRow,
  WhatIfResult,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    headers: { "ngrok-skip-browser-warning": "true" },
  });
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "ngrok-skip-browser-warning": "true",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) {
    let detail = String(res.status);
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  meta: () => get<Meta>("/api/meta"),
  stations: () => get<Station[]>("/api/stations"),
  latestMetrics: () => get<StationMetric[]>("/api/metrics/latest"),
  metricHistory: (hours: number) =>
    get<StationMetric[]>(`/api/metrics/history?hours=${hours}`),
  stationTelemetry: (stationId: string, limit = 200) =>
    get<TelemetryRow[]>(
      `/api/stations/${encodeURIComponent(stationId)}/telemetry?limit=${limit}`,
    ),
  alerts: () => get<Alert[]>("/api/alerts"),
  defects: () => get<{ defects: Defect[]; sankey_edges: SankeyEdge[] }>(
    "/api/defects",
  ),
  recommendations: () => get<Recommendation[]>("/api/recommendations"),
  scenarios: () => get<Scenario[]>("/api/scenarios"),
  confidenceCurve: () =>
    get<ConfidenceCurvePoint[]>("/api/analytics/confidence-curve"),
  whatif: (stationId: string, actionKey: string) =>
    post<WhatIfResult>("/api/whatif/simulate", {
      station_id: stationId,
      action_key: actionKey,
    }),
  plcWrite: (command: string) =>
    post<{ attempted: boolean; raised: string; detail: string }>(
      "/api/plc/write",
      { command },
    ),
  injectScenario: (scenarioKey: string) =>
    post<{ ok: boolean; scenario: string; window_hours: number }>(
      "/api/scenarios/inject",
      { scenario_key: scenarioKey },
    ),
  resetSimulation: () =>
    post<{ ok: boolean; active_scenario: string }>("/api/scenarios/reset"),
};
