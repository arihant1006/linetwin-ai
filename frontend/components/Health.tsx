"use client";

import type { Status } from "@/lib/types";
import { STATUS_COLORS } from "@/lib/constants";

export function HealthBadge({
  status,
  health,
  size = "sm",
}: {
  status: Status;
  health?: number;
  size?: "sm" | "md";
}) {
  const c = STATUS_COLORS[status] ?? "#64748b";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border font-medium ${
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-3 py-1 text-[13px]"
      }`}
      style={{ color: c, borderColor: `${c}55`, background: `${c}14` }}
    >
      <span
        className="inline-block rounded-full"
        style={{ width: 7, height: 7, background: c }}
      />
      {status}
      {health !== undefined && (
        <span className="num opacity-80">{health.toFixed(0)}</span>
      )}
    </span>
  );
}

/** Semi-circular gauge, banded by the four health bands. */
export function HealthGauge({ value }: { value: number }) {
  const v = Math.max(0, Math.min(100, value));
  const R = 70;
  const CX = 90;
  const CY = 88;
  const arc = (from: number, to: number) => {
    const a0 = Math.PI * (1 - from / 50);
    const a1 = Math.PI * (1 - to / 50);
    const x0 = CX + R * Math.cos(a0);
    const y0 = CY - R * Math.sin(a0);
    const x1 = CX + R * Math.cos(a1);
    const y1 = CY - R * Math.sin(a1);
    return `M ${x0} ${y0} A ${R} ${R} 0 0 1 ${x1} ${y1}`;
  };
  // needle angle
  const a = Math.PI * (1 - v / 100);
  const nx = CX + (R - 12) * Math.cos(a);
  const ny = CY - (R - 12) * Math.sin(a);
  return (
    <svg viewBox="0 0 180 108" className="w-full max-w-[220px]">
      <path d={arc(0, 40)} stroke="#ef444433" strokeWidth={13} fill="none" />
      <path d={arc(40, 60)} stroke="#f9731633" strokeWidth={13} fill="none" />
      <path d={arc(60, 80)} stroke="#eab30833" strokeWidth={13} fill="none" />
      <path d={arc(80, 100)} stroke="#22c55e33" strokeWidth={13} fill="none" />
      {/* value arc */}
      <path
        d={arc(0, v)}
        stroke={STATUS_COLORS[
          v >= 80 ? "Healthy" : v >= 60 ? "Watch" : v >= 40 ? "Degraded" : "Critical"
        ]}
        strokeWidth={5}
        fill="none"
        strokeLinecap="round"
      />
      <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e8edf4" strokeWidth={1.6} />
      <circle cx={CX} cy={CY} r={3.4} fill="#e8edf4" />
      <text
        x={CX}
        y={CY - 18}
        textAnchor="middle"
        className="num"
        fontSize={30}
        fontWeight={700}
        fill="#e8edf4"
      >
        {v.toFixed(0)}
      </text>
    </svg>
  );
}
