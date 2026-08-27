"use client";

import { useEffect } from "react";
import {
  useAlerts,
  useMeta,
  useMetricsByStation,
  useStationTelemetry,
  useStations,
} from "@/hooks/useTwin";
import { RootCauseBanner, AlertsPanel } from "@/components/Alerts";
import { StationGrid } from "@/components/StationGrid";
import { StationDetailPanel } from "@/components/StationDetailPanel";
import { ErrorNote, KpiCard, Panel, Spinner } from "@/components/ui";
import { ScenarioStatus } from "@/components/Controls";
import { useTwinStore } from "@/store/useTwinStore";

function weightedVph(rows: { throughput_vph: number; sensor_coverage: number }[]) {
  if (!rows.length) return 0;
  let num = 0;
  let den = 0;
  for (const r of rows) {
    const w = Math.max(r.sensor_coverage || 0.3, 0.05);
    num += r.throughput_vph * w;
    den += w;
  }
  return den ? num / den : 0;
}

export default function SupervisorPage() {
  const stationsQ = useStations();
  const metricsQ = useMetricsByStation();
  const alertsQ = useAlerts();
  const { data: meta } = useMeta();

  const selected = useTwinStore((s) => s.selectedStation);
  const selectStation = useTwinStore((s) => s.selectStation);

  const raw = metricsQ.raw ?? [];
  const topBottleneck =
    [...raw].sort((a, b) => b.bottleneck_prob - a.bottleneck_prob)[0] ?? undefined;

  // Default selection: top bottleneck (same as the Streamlit behavior).
  useEffect(() => {
    if (!selected && topBottleneck) selectStation(topBottleneck.station_id);
  }, [selected, topBottleneck, selectStation]);

  const telemetryQ = useStationTelemetry(selected);
  const stationDef = stationsQ.data?.find((s) => s.station_id === selected);
  const selectedMetric = selected
    ? metricsQ.data.get(selected)
    : undefined;

  if (stationsQ.isLoading || metricsQ.isLoading) return <Spinner label="Loading twin snapshot…" />;
  if (stationsQ.isError || metricsQ.isError)
    return <ErrorNote error={stationsQ.error ?? metricsQ.error} />;

  const vph = weightedVph(raw.map((r) => ({ throughput_vph: r.throughput_vph, sensor_coverage: r.sensor_coverage })));
  const nBneck = raw.filter((r) => r.bottleneck_prob > 0.5).length;
  const nRisk = raw.filter((r) => r.health_score < 60).length;
  const lineHealth = raw.length
    ? raw.reduce((a, r) => a + r.health_score, 0) / raw.length
    : 0;
  const alerts = alertsQ.data ?? [];

  return (
    <div className="flex flex-col gap-4">
      <RootCauseBanner metric={topBottleneck} />
      <ScenarioStatus />

      <div className="grid grid-cols-6 gap-2 max-xl:grid-cols-3 max-sm:grid-cols-2">
        <KpiCard label="Production Rate" value={`${vph.toFixed(1)} vph`} hint="coverage-weighted" />
        <KpiCard
          label="Active Bottlenecks"
          value={String(nBneck)}
          hint="p > 0.50"
          accent={nBneck ? "#ef4444" : "#22c55e"}
        />
        <KpiCard
          label="Stations at Risk"
          value={String(nRisk)}
          hint="health < 60"
          accent={nRisk ? "#f97316" : "#22c55e"}
        />
        <KpiCard label="Open Alerts" value={String(alerts.length)} hint="active" />
        <KpiCard
          label="Vehicles in Line"
          value={(meta?.counts.vehicles ?? 0).toLocaleString()}
          hint="total in window"
        />
        <KpiCard
          label="Overall Line Health"
          value={lineHealth.toFixed(0)}
          hint="mean of 40 stations"
          accent={
            lineHealth >= 80
              ? "#22c55e"
              : lineHealth >= 60
                ? "#eab308"
                : "#ef4444"
          }
        />
      </div>

      <Panel label="Live Station Grid — click a station to inspect">
        <StationGrid
          stations={stationsQ.data ?? []}
          metricsByStation={metricsQ.data}
          selected={selected}
          onSelect={selectStation}
        />
      </Panel>

      <div className="grid grid-cols-[1.5fr_1fr] gap-4 max-lg:grid-cols-1">
        <Panel label={`Station Detail${selected ? ` — ${selected}` : ""}`}>
          {selectedMetric && (
            <StationDetailPanel
              station={stationDef}
              metric={selectedMetric}
              telemetry={telemetryQ.data ?? []}
            />
          )}
        </Panel>
        <Panel label="Active Alerts">
          <AlertsPanel alerts={alerts} onSelectStation={selectStation} />
        </Panel>
      </div>
    </div>
  );
}
