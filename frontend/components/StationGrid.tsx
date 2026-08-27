"use client";

import { motion } from "framer-motion";
import type { StationMetric } from "@/lib/types";
import { STATUS_COLORS, statusBand } from "@/lib/constants";
import type { Station } from "@/lib/types";
import { AREAS } from "@/lib/constants";

/**
 * StationGrid — the 40-station chip grid grouped by area.
 * Health-band color is the load-bearing signal: healthy stations stay quiet,
 * degraded/critical stations are loud. Sparse-telemetry stations get a dashed
 * outline so "dark" stations read as dark even when healthy.
 */
export function StationGrid({
  stations,
  metricsByStation,
  selected,
  onSelect,
}: {
  stations: Station[];
  metricsByStation: Map<string, StationMetric>;
  selected: string | null;
  onSelect: (sid: string) => void;
}) {
  return (
    <div className="flex flex-col gap-3">
      {AREAS.map((area) => {
        const list = stations
          .filter((s) => s.area === area)
          .sort((a, b) => a.sequence - b.sequence);
        if (!list.length) return null;
        return (
          <div key={area}>
            <div className="panel-label mb-1.5">
              {area} · {list.length} stations
            </div>
            <div className="grid grid-cols-10 gap-1.5 max-lg:grid-cols-5">
              {list.map((s) => {
                const m = metricsByStation.get(s.station_id);
                const band = m ? statusBand(m.health_score) : null;
                const c = band ? STATUS_COLORS[band] : "#475569";
                const loud = band === "Degraded" || band === "Critical";
                const isSel = selected === s.station_id;
                const sparse = s.telemetry_class === "sparse";
                return (
                  <motion.button
                    key={s.station_id}
                    whileHover={{ y: -2 }}
                    whileTap={{ scale: 0.96 }}
                    onClick={() => onSelect(s.station_id)}
                    title={`${s.station_name}${m ? ` — ${band}, health ${m.health_score.toFixed(0)}, confidence ${m.confidence.toFixed(0)}%` : ""}`}
                    className={`relative rounded-md border px-1 py-1.5 text-left transition-colors cursor-pointer ${
                      isSel ? "ring-2 ring-accent" : ""
                    }`}
                    style={{
                      borderColor: loud ? `${c}aa` : `${c}44`,
                      background: loud ? `${c}26` : "#171d26",
                      borderStyle: sparse && !loud ? "dashed" : "solid",
                      boxShadow: loud ? `0 0 12px ${c}33` : undefined,
                    }}
                  >
                    <div className="num text-[11px] font-semibold" style={{ color: loud ? c : "#c7d0dd" }}>
                      {s.station_id}
                    </div>
                    <div className="num text-[11px]" style={{ color: m ? c : "#64748b" }}>
                      {m ? m.health_score.toFixed(0) : "--"}
                    </div>
                  </motion.button>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}
