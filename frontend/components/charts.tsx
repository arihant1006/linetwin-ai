"use client";

import { useMemo } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Sankey,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { SankeyEdge, Station, StationMetric } from "@/lib/types";

const tooltipStyle = {
  background: "#171d26",
  border: "1px solid #232c3b",
  borderRadius: 8,
  fontSize: 12,
};

/** Weekly line throughput — hourly mean across stations. */
export function ThroughputTrendChart({ history }: { history: StationMetric[] }) {
  const data = useMemo(() => {
    const byHour = new Map<string, { sum: number; n: number }>();
    for (const r of history) {
      const h = r.bucket_ts.slice(0, 13); // "YYYY-MM-DD HH"
      const e = byHour.get(h) ?? { sum: 0, n: 0 };
      e.sum += r.throughput_vph;
      e.n += 1;
      byHour.set(h, e);
    }
    return [...byHour.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([h, v]) => ({ t: h, vph: +(v.sum / v.n).toFixed(2) }));
  }, [history]);
  if (!data.length) return <div className="text-sm text-mut py-6">No metric history yet.</div>;
  const mean = data.reduce((a, d) => a + d.vph, 0) / data.length;
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 10, bottom: 4, left: -14 }}>
          <CartesianGrid stroke="#232c3b66" />
          <XAxis
            dataKey="t"
            tick={{ fontSize: 10, fill: "#8b98ab" }}
            tickFormatter={(v: string) => v.slice(5, 16)}
            stroke="#232c3b"
          />
          <YAxis tick={{ fontSize: 10, fill: "#8b98ab" }} stroke="#232c3b" />
          <Tooltip contentStyle={tooltipStyle} />
          <ReferenceLine
            y={mean}
            stroke="#66738a"
            strokeDasharray="4 4"
            label={{ value: `mean ${mean.toFixed(0)}`, fontSize: 10, fill: "#8b98ab" }}
          />
          <Line type="monotone" dataKey="vph" stroke="#22d3ee" strokeWidth={2} dot={false} name="line vph" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Avg cycle time by area over the trailing window (30-min buckets). */
export function CycleTimeByAreaChart({
  history,
  stations,
}: {
  history: StationMetric[];
  stations: Station[];
}) {
  const areaMap = useMemo(
    () => new Map(stations.map((s) => [s.station_id, s.area])),
    [stations],
  );
  const palette: Record<string, string> = {
    "Body Shop": "#22d3ee",
    "Paint Shop": "#a78bfa",
    "Final Assembly": "#f59e0b",
  };
  const series = useMemo(() => {
    type E = Record<string, number | string>;
    const byBucketArea = new Map<string, Map<string, { sum: number; n: number }>>();
    for (const r of history) {
      const area = areaMap.get(r.station_id);
      if (!area) continue;
      // floor ts to 30 min
      const [d, hms] = r.bucket_ts.split(" ");
      const [H, M] = hms.split(":").map(Number);
      const bucket = `${d} ${String(H).padStart(2, "0")}:${M < 30 ? "00" : "30"}`;
      const perArea = byBucketArea.get(bucket) ?? new Map();
      const e = perArea.get(area) ?? { sum: 0, n: 0 };
      e.sum += r.avg_cycle_time;
      e.n += 1;
      perArea.set(area, e);
      byBucketArea.set(bucket, perArea);
    }
    return [...byBucketArea.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map<E>(([bucket, perArea]) => {
        const row: E = { t: bucket };
        for (const [area, v] of perArea) row[area] = +(v.sum / v.n).toFixed(1);
        return row;
      });
  }, [history, areaMap]);

  if (!series.length) return <div className="text-sm text-mut py-6">No metric history yet.</div>;
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series} margin={{ top: 8, right: 10, bottom: 4, left: -14 }}>
          <CartesianGrid stroke="#232c3b66" />
          <XAxis
            dataKey="t"
            tick={{ fontSize: 10, fill: "#8b98ab" }}
            tickFormatter={(v: string) => v.slice(11)}
            stroke="#232c3b"
          />
          <YAxis tick={{ fontSize: 10, fill: "#8b98ab" }} stroke="#232c3b" />
          <Tooltip contentStyle={tooltipStyle} />
          {Object.entries(palette).map(([area, color]) => (
            <Line key={area} type="monotone" dataKey={area} stroke={color} strokeWidth={1.8} dot={false} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
      <Legend items={Object.entries(palette).map(([k, v]) => ({ label: k, color: v }))} />
    </div>
  );
}

export function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1">
      {items.map((i) => (
        <span key={i.label} className="inline-flex items-center gap-1.5 text-[10px] text-mut">
          <span className="h-2 w-2 rounded-full" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  );
}

/** Bottleneck pressure Pareto — top 10 by bottleneck_prob × queue_pressure. */
export function BottleneckPareto({ metrics }: { metrics: StationMetric[] }) {
  const data = useMemo(
    () =>
      [...metrics]
        .map((r) => ({
          station: r.station_id,
          score: +(r.bottleneck_prob * r.queue_pressure).toFixed(3),
          prob: r.bottleneck_prob,
        }))
        .sort((a, b) => b.score - a.score)
        .slice(0, 10)
        .reverse(),
    [metrics],
  );
  if (!data.length) return null;
  return (
    <div style={{ height: 280 }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 4, right: 24, bottom: 4, left: 8 }}>
          <XAxis type="number" tick={{ fontSize: 10, fill: "#8b98ab" }} stroke="#232c3b" />
          <YAxis
            type="category"
            dataKey="station"
            tick={{ fontSize: 11, fill: "#c7d0dd", fontFamily: "var(--font-mono)" }}
            stroke="#232c3b"
            width={44}
          />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value, _n, item) => [
              `${Number(value).toFixed(3)} (p=${((item?.payload as { prob: number })?.prob * 100).toFixed(0)}%)`,
              "pressure",
            ]}
          />
          <Bar dataKey="score" fill="#f97316" radius={[0, 3, 3, 0]} barSize={14} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Defect propagation Sankey (origin → … → detection).
 * Edges come precomputed from the API (sankey_edges on real defect chains).
 */
interface SankeyNode { name: string }
export function PropagationSankey({ edges }: { edges: SankeyEdge[] }) {
  if (!edges.length) {
    return (
      <div className="text-sm text-mut py-6">
        No defect chains in the current window.
      </div>
    );
  }
  const nodes: SankeyNode[] = [];
  const idx = new Map<string, number>();
  for (const e of edges) {
    for (const n of [e.source, e.target]) {
      if (!idx.has(n)) {
        idx.set(n, nodes.length);
        nodes.push({ name: n });
      }
    }
  }
  const links = edges.map((e) => ({
    source: idx.get(e.source)!,
    target: idx.get(e.target)!,
    value: e.value,
  }));
  return (
    <div style={{ height: 320 }}>
      <style>{`.recharts-sankey-node text { fill: #e8edf4; font-size: 11px; font-family: var(--font-mono); }`}</style>
      <ResponsiveContainer width="100%" height="100%">
        <Sankey
          data={{ nodes, links }}
          nodePadding={18}
          nodeWidth={12}
          link={{ stroke: "#22d3ee", strokeOpacity: 0.25, fill: "#22d3ee", fillOpacity: 0.18 }}
          margin={{ top: 8, right: 90, bottom: 8, left: 10 }}
        >
          <Tooltip contentStyle={tooltipStyle} />
        </Sankey>
      </ResponsiveContainer>
    </div>
  );
}

/**
 * Missing-data experiment: confidence curve from the twin's own
 * compute_confidence vs a flat contextual-detection proxy. Illustrative.
 */
export function MissingDataLab({
  curve,
}: {
  curve: { coverage: number; confidence: number; detection_proxy: number }[];
}) {
  if (!curve.length) return null;
  return (
    <div style={{ height: 260 }}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={curve} margin={{ top: 8, right: 12, bottom: 18, left: -8 }}>
          <CartesianGrid stroke="#232c3b66" />
          <XAxis
            dataKey="coverage"
            tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
            tick={{ fontSize: 10, fill: "#8b98ab" }}
            stroke="#232c3b"
            label={{ value: "Synthetic sensor coverage", fontSize: 10, fill: "#8b98ab", position: "insideBottom", offset: -10 }}
          />
          <YAxis domain={[0, 105]} tick={{ fontSize: 10, fill: "#8b98ab" }} stroke="#232c3b" />
          <Tooltip
            contentStyle={tooltipStyle}
            formatter={(value, name) => [`${Number(value).toFixed(1)}`, String(name)]}
            labelFormatter={(label) => `coverage ${Math.round(Number(label) * 100)}%`}
          />
          <Line type="monotone" dataKey="confidence" stroke="#22d3ee" strokeWidth={2} dot={{ r: 3 }} name="Predicted confidence" />
          <Line
            type="monotone"
            dataKey="detection_proxy"
            stroke="#f59e0b"
            strokeWidth={1.6}
            strokeDasharray="4 4"
            dot={{ r: 3 }}
            name="Detection capability proxy (context-only)"
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
