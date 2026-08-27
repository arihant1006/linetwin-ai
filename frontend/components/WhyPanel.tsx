"use client";

import type { ExplanationEntry } from "@/lib/types";
import { CoverageBar } from "./Confidence";

/**
 * WhyPanel — the product's differentiator, first-class.
 * Renders the twin's full per-station explanation breakdown verbatim
 * (factor / detail / weight), persisted from inference at scoring time.
 */
export function WhyPanel({
  stationId,
  status,
  explanation,
  coverage,
  confidence,
}: {
  stationId: string;
  status: string;
  explanation: ExplanationEntry[];
  coverage: number;
  confidence: number;
}) {
  return (
    <div className="rounded-lg border border-accent/30 bg-accent/[0.05] p-3">
      <div className="flex items-center justify-between gap-2 mb-2.5">
        <span className="text-[13px] font-bold tracking-wide text-accent">
          WHY {status.toUpperCase()} — {stationId}
        </span>
        <CoverageBar value={coverage} label="effective coverage" width={90} />
      </div>
      <div className="flex flex-col gap-2">
        {explanation.length === 0 && (
          <span className="text-xs text-mut">
            No explanation stored for this bucket.
          </span>
        )}
        {explanation.map((e, i) => (
          <div key={i} className="grid grid-cols-[minmax(140px,190px)_1fr_auto] items-baseline gap-x-3 gap-y-0 max-md:grid-cols-1">
            <span className="text-[12px] font-semibold text-txt/90 leading-snug">
              {e.factor}
            </span>
            <span className="text-[12px] text-mut leading-snug">{e.detail}</span>
            <span className="w-16 hidden md:block" title={`weight ${e.weight.toFixed(2)}`}>
              <WeightMeter weight={e.weight} />
            </span>
          </div>
        ))}
      </div>
      <div className="mt-2.5 text-[11px] text-mut border-t border-line pt-2">
        Confidence {confidence.toFixed(0)}% — computed from effective sensor
        coverage, evidence agreement and data volume (compute_confidence). A
        sensor-poor station with strong contextual agreement still earns high
        confidence.
      </div>
    </div>
  );
}

function WeightMeter({ weight }: { weight: number }) {
  const w = Math.max(0, Math.min(1, weight));
  return (
    <span className="block h-1.5 rounded bg-line overflow-hidden">
      <span
        className="block h-full rounded"
        style={{ width: `${w * 100}%`, background: "#22d3ee" }}
      />
    </span>
  );
}
