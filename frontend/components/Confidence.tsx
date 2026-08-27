"use client";

/**
 * ConfidenceIndicator — the twin's "how sure am I" channel.
 * Deliberately rendered in the cyan/steel family (never health-band colors)
 * so viewers learn to read certainty as a separate visual channel.
 *
 * - `ConfidenceRing`: radial ring, 0-100.
 * - `CoverageBar`: segmented sensor-coverage bar with per-segment dropout gaps
 *   to evoke "dark sensors".
 */

function confColor(v: number): string {
  return v >= 70 ? "#67e8f9" : v >= 40 ? "#38bdf8" : "#64748b";
}

export function ConfidenceRing({
  value,
  size = 44,
  label,
}: {
  value: number; // 0-100
  size?: number;
  label?: string;
}) {
  const v = Math.max(0, Math.min(100, value));
  const R = (size - 7) / 2;
  const C = 2 * Math.PI * R;
  const color = confColor(v);
  return (
    <span className="inline-flex items-center gap-1.5">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={R}
          fill="none"
          stroke="#232c3b"
          strokeWidth={4}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={R}
          fill="none"
          stroke={color}
          strokeWidth={4}
          strokeLinecap="round"
          strokeDasharray={`${(C * v) / 100} ${C}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x="50%"
          y="54%"
          textAnchor="middle"
          dominantBaseline="middle"
          fontSize={size * 0.3}
          fontWeight={700}
          fill={color}
          className="num"
        >
          {v.toFixed(0)}
        </text>
      </svg>
      {label && <span className="panel-label">{label}</span>}
    </span>
  );
}

export function CoverageBar({
  value,
  width = 64,
  label,
}: {
  value: number; // 0-1 effective coverage
  width?: number;
  label?: string;
}) {
  const pct = Math.max(0, Math.min(1, value));
  const segments = 10;
  const lit = Math.round(pct * segments);
  const color = confColor(pct * 100);
  return (
    <span className="inline-flex flex-col gap-0.5" title={`Sensor coverage ${(pct * 100).toFixed(0)}%`}>
      <span className="flex gap-[2px]" style={{ width }}>
        {Array.from({ length: segments }, (_, i) => (
          <span
            key={i}
            className="flex-1 rounded-[1px]"
            style={{
              height: 6,
              background:
                i < lit ? color : "#232c3b",
              opacity: i < lit ? 1 : 1,
            }}
          />
        ))}
      </span>
      {label && (
        <span className="num text-[10px]" style={{ color }}>
          {(pct * 100).toFixed(0)}% {label}
        </span>
      )}
    </span>
  );
}

/** Compact paired display used in KPI tiles & matrix rows. */
export function ConfidenceCoverage({
  confidence,
  coverage,
}: {
  confidence: number;
  coverage: number;
}) {
  return (
    <span className="inline-flex items-center gap-3">
      <ConfidenceRing value={confidence} size={34} />
      <CoverageBar value={coverage} />
    </span>
  );
}
