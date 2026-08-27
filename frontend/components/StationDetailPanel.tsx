"use client";

import type { Station, StationMetric, TelemetryRow } from "@/lib/types";
import { STATE_COLORS } from "@/lib/constants";
import { HealthBadge, HealthGauge } from "./Health";
import { ConfidenceRing, CoverageBar } from "./Confidence";
import { WhyPanel } from "./WhyPanel";
import { KpiCard } from "./ui";
import {
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const CHANNEL_COLORS: Record<string, string> = {
  cycle_time: "#22d3ee",
  torque: "#a78bfa",
  vibration: "#f59e0b",
  temperature: "#22c55e",
  motor_current: "#ef4444",
  pressure: "#38bdf8",
};

function MachineStateStrip({ rows }: { rows: TelemetryRow[] }) {
  const states = rows.filter((r) => r.machine_state);
  if (!states.length) return null;
  const order = ["RUNNING", "STARVED", "BLOCKED", "MAINTENANCE", "CHANGEOVER"];
  const n = states.length;
  // SVG with preserveAspectRatio="none": every visit gets exactly 1/n of the
  // width, so the strip can never overflow its panel regardless of row count.
  return (
    <div>
      <div className="panel-label mb-1">Machine state (recent)</div>
      <svg
        viewBox={`0 0 ${n} 10`}
        preserveAspectRatio="none"
        className="w-full h-9 block"
      >
        {states.map((r, i) => {
          const running = r.machine_state === "RUNNING";
          const minor =
            r.machine_state === "CHANGEOVER" || r.machine_state === "MAINTENANCE";
          return (
            <rect
              key={i}
              x={i}
              width={1.02} // slight overlap avoids hairline gaps between rects
              y={running ? 0 : minor ? 4 : 2}
              height={running ? 10 : minor ? 6 : 8}
              fill={STATE_COLORS[r.machine_state] ?? "#64748b"}
              opacity={0.85}
            >
              <title>{`${r.ts} · ${r.machine_state}${r.vehicle_model ? ` · ${r.vehicle_model}` : ""}`}</title>
            </rect>
          );
        })}
      </svg>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1">
        {order.map((s) => (
          <span key={s} className="inline-flex items-center gap-1 text-[10px] text-mut">
            <span className="h-2 w-2 rounded-full" style={{ background: STATE_COLORS[s] }} />
            {s}
          </span>
        ))}
        <span className="text-[10px] text-mut/70 ml-auto">{n} visits</span>
      </div>
    </div>
  );
}

function SensorChannels({ rows }: { rows: TelemetryRow[] }) {
  const channels = ["cycle_time", "torque", "vibration", "temperature", "motor_current", "pressure"];
  const active = channels.filter(
    (c) => rows.some((r) => r[c as keyof TelemetryRow] != null),
  );
  if (!active.length) {
    return (
      <div className="text-xs text-mut py-3">
        No direct sensor channels reporting for this station — the twin is
        inferring from context only.
      </div>
    );
  }
  // Channels have incompatible units (seconds, Nm, °C…), so each is plotted
  // normalized to its own window mean (100% = nominal for that channel).
  const means: Record<string, number> = {};
  for (const c of active) {
    let sum = 0;
    let n = 0;
    for (const r of rows) {
      const v = (r as unknown as Record<string, number | null>)[c];
      if (v != null && Number.isFinite(v)) {
        sum += v;
        n += 1;
      }
    }
    means[c] = n ? sum / n : 1;
  }
  const data = rows.map((r, i) => {
    const rec = r as unknown as Record<string, number | null>;
    const point: Record<string, number | null> = { i };
    for (const c of active) {
      const v = rec[c];
      point[c] = v != null && means[c] > 0 ? +((v / means[c]) * 100).toFixed(1) : null;
    }
    return point;
  });
  return (
    <div>
      <div style={{ height: 190 }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -18 }}>
            <XAxis dataKey="i" hide />
            <YAxis
              tick={{ fontSize: 10, fill: "#8b98ab" }}
              stroke="#232c3b"
              width={42}
              tickFormatter={(v: number) => `${v}%`}
              domain={[50, 160]}
            />
            <Tooltip
              contentStyle={{
                background: "#171d26",
                border: "1px solid #232c3b",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={() => ""}
              formatter={(value, name) => [`${Number(value).toFixed(1)}%`, String(name)]}
            />
            <ReferenceLine y={100} stroke="#33415c" strokeDasharray="4 4" />
            {active.map((c) => (
              <Line
                key={c}
                type="monotone"
                dataKey={c}
                stroke={CHANNEL_COLORS[c]}
                strokeWidth={1.4}
                dot={false}
                connectNulls
              />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-x-3 mt-1">
        {active.map((c) => (
          <span key={c} className="inline-flex items-center gap-1 text-[10px] text-mut">
            <span className="h-2 w-2 rounded-full" style={{ background: CHANNEL_COLORS[c] }} />
            {c}
          </span>
        ))}
        <span className="text-[10px] text-mut/70 ml-auto">
          normalized to window mean · dashed line = nominal
        </span>
      </div>
    </div>
  );
}

export function StationDetailPanel({
  station,
  metric,
  telemetry,
}: {
  station?: Station;
  metric?: StationMetric;
  telemetry: TelemetryRow[];
}) {
  if (!metric) {
    return (
      <div className="text-sm text-mut py-6">
        No twin state yet for this station.
      </div>
    );
  }
  const target = station?.cycle_time_target;
  const actual = metric.avg_cycle_time;
  const barMax = Math.max(target ?? 0, actual) * 1.15;
  return (
    <div className="flex flex-col gap-4">
      <header className="flex items-center justify-between gap-2 flex-wrap">
        <div>
          <h2 className="num text-lg font-bold">
            {metric.station_id}
            <span className="text-mut font-normal text-sm ml-2">
              {station?.station_name}
            </span>
          </h2>
          <span className="text-xs text-mut">
            {station?.area} · {station?.station_type} ·{" "}
            <span className="capitalize">{station?.telemetry_class}</span>{" "}
            telemetry
          </span>
        </div>
        <HealthBadge status={metric.status} size="md" />
      </header>

      <div className="grid grid-cols-[220px_1fr] gap-4 max-md:grid-cols-1">
        <div className="card p-3 flex flex-col items-center">
          <div className="panel-label self-start mb-1">Health score</div>
          <HealthGauge value={metric.health_score} />
        </div>
        <div className="grid grid-cols-2 gap-2 content-start">
          <KpiCard
            label="Confidence"
            value={<ConfidenceRing value={metric.confidence} size={40} />}
            hint="tied to coverage + agreement"
          />
          <KpiCard
            label="Bottleneck prob"
            value={`${(metric.bottleneck_prob * 100).toFixed(0)}%`}
            hint={metric.bottleneck_prob > 0.5 ? "predicted constraint" : undefined}
            accent={metric.bottleneck_prob > 0.5 ? "#ef4444" : undefined}
          />
          <KpiCard
            label="Sensor coverage"
            value={<CoverageBar value={metric.sensor_coverage} width={90} label="" />}
            hint={`effective ${(metric.sensor_coverage * 100).toFixed(0)}%`}
          />
          <KpiCard
            label="CT deviation"
            value={`${metric.ct_deviation_pct >= 0 ? "+" : ""}${metric.ct_deviation_pct.toFixed(1)}%`}
            hint="vs mix-adjusted baseline"
            accent={Math.abs(metric.ct_deviation_pct) > 10 ? "#f97316" : undefined}
          />
          {/* target vs actual cycle time */}
          <div className="col-span-2 card px-4 py-3">
            <div className="panel-label mb-2">Cycle time — target vs actual</div>
            {target && actual > 0 && (
              <div className="flex flex-col gap-1.5">
                <Bar label="Target" value={target} max={barMax} color="#334155" text={`${target.toFixed(0)}s`} />
                <Bar
                  label="Actual"
                  value={actual}
                  max={barMax}
                  color={actual > target * 1.08 ? "#f97316" : "#22d3ee"}
                  text={`${actual.toFixed(0)}s`}
                />
              </div>
            )}
          </div>
        </div>
      </div>

      <WhyPanel
        stationId={metric.station_id}
        status={metric.status}
        explanation={metric.explanation}
        coverage={metric.sensor_coverage}
        confidence={metric.confidence}
      />

      {telemetry.length > 0 && (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <MachineStateStrip rows={telemetry} />
          <SensorChannels rows={telemetry} />
        </div>
      )}
    </div>
  );
}

function Bar({
  label,
  value,
  max,
  color,
  text,
}: {
  label: string;
  value: number;
  max: number;
  color: string;
  text: string;
}) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 text-[11px] text-mut">{label}</span>
      <div className="flex-1 h-5 rounded bg-line/50 overflow-hidden relative">
        <div
          className="h-full rounded flex items-center justify-end pr-1.5"
          style={{ width: `${(value / max) * 100}%`, background: color }}
        >
          <span className="num text-[10px] font-semibold text-bg">{text}</span>
        </div>
      </div>
    </div>
  );
}
