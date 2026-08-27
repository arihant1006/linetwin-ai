"use client";

import { motion } from "framer-motion";
import type { Alert, StationMetric } from "@/lib/types";
import { CoverageBar } from "./Confidence";

const SEV = {
  CRITICAL: { color: "#ef4444", icon: "🚨" },
  WARNING: { color: "#eab308", icon: "⚠️" },
  INFO: { color: "#64748b", icon: "ℹ️" },
} as const;

/** Alarm strip for the top predicted bottleneck — the most important element
 *  on the supervisor screen when active. */
export function RootCauseBanner({ metric }: { metric?: StationMetric }) {
  if (!metric || metric.bottleneck_prob <= 0.55) return null;
  const impact = Math.round(-(metric.bottleneck_prob * 20));
  const critical = metric.bottleneck_prob > 0.7;
  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-1"
      style={{
        borderColor: critical ? "#ef4444" : "#f97316",
        background: critical
          ? "linear-gradient(90deg, rgba(239,68,68,.18), rgba(23,29,38,.9) 65%)"
          : "linear-gradient(90deg, rgba(249,115,22,.16), rgba(23,29,38,.9) 65%)",
        boxShadow: `0 0 24px ${critical ? "#ef444433" : "#f9731622"}`,
      }}
    >
      <span className={`text-[13px] font-bold tracking-wide ${critical ? "text-critical" : "text-degraded"}`}>
        🎯 PREDICTED BOTTLENECK
      </span>
      <span className="num text-xl font-bold">{metric.station_id}</span>
      <span className="text-[13px] text-mut">
        Confidence <b className="num text-txt">{metric.confidence.toFixed(0)}%</b>
      </span>
      <span className="text-[13px] text-mut">
        Sensor coverage{" "}
        <b className="num text-txt">{(metric.sensor_coverage * 100).toFixed(0)}%</b>
      </span>
      <span className="text-[13px] text-mut">
        Est. throughput impact{" "}
        <b className="num text-critical">{impact}%</b>
      </span>
    </motion.div>
  );
}

export function AlertsPanel({
  alerts,
  onSelectStation,
  max = 14,
}: {
  alerts: Alert[];
  onSelectStation?: (sid: string) => void;
  max?: number;
}) {
  if (!alerts.length) {
    return <div className="text-sm text-mut py-4">No active alerts. Line is quiet.</div>;
  }
  return (
    <div className="flex flex-col gap-1.5 overflow-y-auto max-h-[520px] pr-1">
      {alerts.slice(0, max).map((a) => {
        const sev = SEV[a.severity] ?? SEV.INFO;
        return (
          <button
            key={a.alert_id}
            onClick={() => a.station_id && onSelectStation?.(a.station_id)}
            className="text-left card px-3 py-2 border-l-[3px] hover:border-line-strong transition-colors cursor-pointer"
            style={{ borderLeftColor: sev.color }}
          >
            <div className="text-[12.5px] leading-snug">
              {sev.icon} <b className="num">{a.station_id}</b> — {a.message}
            </div>
            <div className="mt-1.5 flex items-center gap-3">
              <CoverageBar value={a.sensor_coverage} width={54} />
              <span className="num text-[10px] text-mut">conf {(a.confidence * 100).toFixed(0)}%</span>
              {a.causes.length > 0 && (
                <span className="text-[10px] text-sky-300/80 truncate">
                  {a.causes.slice(0, 2).join(" · ")}
                </span>
              )}
            </div>
          </button>
        );
      })}
    </div>
  );
}
