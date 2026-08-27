"use client";

import { useState } from "react";
import {
  useConfidenceCurve,
  useDefects,
  useHistory,
  useMetricsByStation,
  useStations,
} from "@/hooks/useTwin";
import { ErrorNote, Panel, Spinner } from "@/components/ui";
import {
  BottleneckPareto,
  CycleTimeByAreaChart,
  MissingDataLab,
  PropagationSankey,
  ThroughputTrendChart,
} from "@/components/charts";
import { STATUS_COLORS, statusBand } from "@/lib/constants";
import { ConfidenceRing, CoverageBar } from "@/components/Confidence";

const TABS = [
  ["trends", "Throughput & Cycle Time"],
  ["prop", "Defect Propagation"],
  ["matrix", "Station Matrix"],
  ["pareto", "Bottleneck Pareto"],
  ["lab", "Missing-Data Experiment"],
] as const;

export default function ManagerPage() {
  const stationsQ = useStations();
  const metricsQ = useMetricsByStation();
  const hist168 = useHistory(168);
  const hist24 = useHistory(24);
  const defectsQ = useDefects();
  const curveQ = useConfidenceCurve();
  const [tab, setTab] = useState<(typeof TABS)[number][0]>("trends");

  if (stationsQ.isLoading || metricsQ.isLoading)
    return <Spinner label="Loading plant analytics…" />;
  if (stationsQ.isError) return <ErrorNote error={stationsQ.error} />;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-1 border-b border-line overflow-x-auto">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`px-3.5 py-2 text-[13px] font-medium -mb-px border-b-2 transition-colors cursor-pointer whitespace-nowrap ${
              tab === key
                ? "border-accent text-accent"
                : "border-transparent text-mut hover:text-txt"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "trends" && (
        <div className="grid grid-cols-2 gap-4 max-lg:grid-cols-1">
          <Panel label="Throughput — last 7 days (vehicles/hour, whole line)">
            <ThroughputTrendChart history={hist168.data ?? []} />
          </Panel>
          <Panel label="Avg cycle time by area — last 24h">
            <CycleTimeByAreaChart
              history={hist24.data ?? []}
              stations={stationsQ.data ?? []}
            />
          </Panel>
        </div>
      )}

      {tab === "prop" && (
        <Panel label="Defect propagation pattern (origin → detection)">
          <p className="text-xs text-mut mb-3">
            Statistical re-simulation of plausible downstream propagation paths
            given each defect&apos;s origin and detection point — a propagation
            pattern across the window, not an individual vehicle trace.
          </p>
          <PropagationSankey edges={defectsQ.data?.sankey_edges ?? []} />
        </Panel>
      )}

      {tab === "matrix" && (
        <Panel label="Station matrix — sorted by health">
          <StationMatrix
            stations={stationsQ.data ?? []}
            metrics={[...metricsQ.data.values()]}
          />
        </Panel>
      )}

      {tab === "pareto" && (
        <Panel label="Bottleneck pressure — top 10 (prob × queue pressure)">
          <BottleneckPareto metrics={[...metricsQ.data.values()]} />
        </Panel>
      )}

      {tab === "lab" && (
        <div className="grid grid-cols-[1fr_1fr] gap-4 max-lg:grid-cols-1">
          <Panel label="Sensor coverage vs prediction confidence (illustrative experiment)">
            <p className="text-xs text-mut mb-3">
              The confidence curve is computed live with the twin&apos;s own{" "}
              <code className="num">compute_confidence</code> formula
              (obs_n=40, agreement=0.8, history=48). Contextual detection
              capability is held at full strength as a flat proxy — this chart
              demonstrates the design intent: confidence degrades gracefully
              while context-aware inference keeps working.
            </p>
            <MissingDataLab curve={curveQ.data ?? []} />
          </Panel>
          <Panel label="Why this matters">
            <div className="text-sm leading-relaxed text-mut flex flex-col gap-3 pt-1">
              <p>
                Real lines are never uniformly instrumented — in this plant,
                16 stations are rich, 14 medium, 10 sparse. A traditional
                threshold monitor goes blind exactly where the risk is.
              </p>
              <p>
                LineTwin keeps scoring every station by fusing flow context:
                upstream queues, downstream starvation, neighbor health, manual
                checklists — and attaches an explicit confidence to every score.
              </p>
              <p>
                Even at 10% sensor coverage the model retains meaningful
                confidence when contextual signals agree — that is the core
                claim under test here, and it holds in the live scenario
                demos (e.g. B07 degradation under heavy sensor dropout).
              </p>
            </div>
          </Panel>
        </div>
      )}
    </div>
  );
}

function StationMatrix({
  stations,
  metrics,
}: {
  stations: import("@/lib/types").Station[];
  metrics: import("@/lib/types").StationMetric[];
}) {
  const rows = [...metrics]
    .sort((a, b) => a.health_score - b.health_score)
    .map((m) => ({
      m,
      station: stations.find((s) => s.station_id === m.station_id),
    }));
  return (
    <div className="overflow-auto max-h-[600px]">
      <table className="w-full text-[12px] border-collapse">
        <thead className="sticky top-0 bg-card z-10">
          <tr className="text-left panel-label [&>th]:py-2 [&>th]:px-2.5 [&>th]:border-b [&>th]:border-line">
            <th>Station</th>
            <th>Name</th>
            <th>Status</th>
            <th className="!text-right">Health</th>
            <th className="!text-right">Bottleneck p</th>
            <th className="!text-right">Defect %</th>
            <th className="!text-right">Avg CT</th>
            <th>Coverage</th>
            <th>Confidence</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ m, station }) => {
            const band = statusBand(m.health_score);
            const c = STATUS_COLORS[band];
            return (
              <tr key={m.station_id} className="[&>td]:py-1.5 [&>td]:px-2.5 hover:bg-card-raised">
                <td className="num font-semibold">{m.station_id}</td>
                <td className="text-mut truncate max-w-[170px]">{station?.station_name}</td>
                <td>
                  <span
                    className="inline-flex items-center gap-1.5"
                    style={{ color: c }}
                  >
                    <span className="h-2 w-2 rounded-full" style={{ background: c }} />
                    {band}
                  </span>
                </td>
                <td className="num !text-right font-semibold" style={{ background: `${c}18`, borderRadius: 4 }}>
                  {m.health_score.toFixed(1)}
                </td>
                <td className="num !text-right">{(m.bottleneck_prob * 100).toFixed(0)}%</td>
                <td className="num !text-right">{(m.defect_rate * 100).toFixed(2)}</td>
                <td className="num !text-right">{m.avg_cycle_time.toFixed(1)}s</td>
                <td><CoverageBar value={m.sensor_coverage} width={56} /></td>
                <td><ConfidenceRing value={m.confidence} size={30} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
