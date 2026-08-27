"use client";

import { useMemo, useState } from "react";
import {
  useHistory,
  useLatestMetrics,
} from "@/hooks/useTwin";
import { ErrorNote, KpiCard, Panel, Spinner } from "@/components/ui";
import {
  DOWNTIME_COST_HR,
  DEFECT_COST,
  VEHICLE_VALUE,
  fmtInr,
} from "@/lib/constants";

function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="panel-label">{label}</span>
      <input
        type="number"
        className="num bg-card-raised border border-line rounded-md px-2.5 py-2 text-[14px] outline-none focus:border-accent/60"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
      />
    </label>
  );
}

export default function LeadershipPage() {
  const metricsQ = useLatestMetrics();
  const hist24 = useHistory(24);

  const stats = useMemo(() => {
    const raw = metricsQ.data ?? [];
    let num = 0;
    let den = 0;
    for (const r of raw) {
      const w = Math.max(r.sensor_coverage || 0.3, 0.05);
      num += r.throughput_vph * w;
      den += w;
    }
    const vph = den ? num / den : 0;
    const defectPct = raw.length
      ? (raw.reduce((a, r) => a + r.defect_rate, 0) / raw.length) * 100
      : 0;
    // starvation minutes/day proxy: mean starv rate per bucket * 60 min
    const hist = hist24.data ?? [];
    const byBucket = new Map<string, { sum: number; n: number }>();
    for (const r of hist) {
      const e = byBucket.get(r.bucket_ts) ?? { sum: 0, n: 0 };
      e.sum += r.starvation_rate;
      e.n += 1;
      byBucket.set(r.bucket_ts, e);
    }
    let starveMinDay = 0;
    for (const e of byBucket.values()) starveMinDay += (e.sum / e.n) * 60.0;
    const downtimeHrsDay = starveMinDay / 60.0;
    const defectsPerYear = (defectPct / 100) * vph * 16 * 300;
    const annualLoss =
      downtimeHrsDay * 300 * DOWNTIME_COST_HR + defectsPerYear * DEFECT_COST;
    return {
      vehToday: vph * 16,
      vph,
      defectPct,
      starveMinDay,
      downtimeHrsDay,
      defectsPerYear,
      annualLoss,
    };
  }, [metricsQ.data, hist24.data]);

  // ROI inputs — all illustrative assumptions, user-editable.
  const [vehDay, setVehDay] = useState<number>(480);
  const [prodDays, setProdDays] = useState(300);
  const [valVeh, setValVeh] = useState(VEHICLE_VALUE);
  const [dtCost, setDtCost] = useState(DOWNTIME_COST_HR);
  const [defCost, setDefCost] = useState(DEFECT_COST);
  const [depCost, setDepCost] = useState(4_200_000);

  if (metricsQ.isLoading) return <Spinner label="Loading plant KPIs…" />;
  if (metricsQ.isError) return <ErrorNote error={metricsQ.error} />;

  // Fixed illustrative improvement percentages — assumptions, NOT measured.
  const dtHoursSavedYr = stats.downtimeHrsDay * prodDays * 0.32;
  const defectsPreventedYr = stats.defectsPerYear * 0.41;
  const extraVehiclesYr = vehDay * prodDays * 0.09;
  const benefit =
    dtHoursSavedYr * dtCost + defectsPreventedYr * defCost + extraVehiclesYr * valVeh;
  const roiPct = depCost > 0 ? ((benefit - depCost) / depCost) * 100 : 0;
  const paybackMonths = benefit > 0 ? depCost / (benefit / 12) : Infinity;

  return (
    <div className="flex flex-col gap-5 max-w-[1200px] mx-auto">
      <Panel label="Plant at a glance (live twin snapshot)">
        <div className="grid grid-cols-4 gap-3 max-lg:grid-cols-2">
          <KpiCard
            label="Line Throughput Today"
            value={`${stats.vehToday.toLocaleString()} veh`}
            hint={`${stats.vph.toFixed(1)} vph × 16h shift`}
          />
          <KpiCard
            label="Defect Rate"
            value={`${stats.defectPct.toFixed(2)}%`}
            hint="fleet mean, current window"
          />
          <KpiCard
            label="Downtime Proxy"
            value={`${Math.round(stats.starveMinDay).toLocaleString()} min`}
            hint="starved minutes / 24h"
          />
          <KpiCard
            label="Estimated Annual Loss"
            value={fmtInr(stats.annualLoss)}
            hint={`${stats.downtimeHrsDay.toFixed(1)} down-hrs/day × 300d + defects`}
            accent="#ef4444"
          />
        </div>
      </Panel>

      <section className="grid grid-cols-3 gap-4 max-md:grid-cols-1">
        {[
          { pct: "32%", lbl: "Potential downtime reduction" },
          { pct: "41%", lbl: "Defect reduction" },
          { pct: "9%", lbl: "Throughput increase" },
        ].map((c) => (
          <div
            key={c.lbl}
            className="card p-6 text-center relative overflow-hidden"
          >
            <div
              className="absolute inset-x-0 top-0 h-[3px]"
              style={{ background: "linear-gradient(90deg,#22d3ee88,#22d3ee11)" }}
            />
            <span className="inline-block mb-2 rounded px-2 py-0.5 text-[10px] font-bold tracking-widest bg-amber-400/10 text-amber-300 border border-amber-300/30">
              ILLUSTRATIVE ASSUMPTION
            </span>
            <div className="num text-[44px] leading-none font-bold text-accent">
              {c.pct}
            </div>
            <div className="text-mut text-[13px] mt-2">{c.lbl}</div>
          </div>
        ))}
      </section>

      <Panel label="ROI calculator — edit the assumptions">
        <div className="grid grid-cols-6 gap-3 max-xl:grid-cols-3 max-sm:grid-cols-2">
          <NumberField label="Vehicles / day" value={vehDay} onChange={(v) => setVehDay(Math.max(v || 0, 0))} min={10} max={5000} step={10} />
          <NumberField label="Production days / year" value={prodDays} onChange={setProdDays} min={50} max={365} />
          <NumberField label="Value / vehicle (₹)" value={valVeh} onChange={setValVeh} min={100_000} max={5_000_000} step={25_000} />
          <NumberField label="Downtime cost / hour (₹)" value={dtCost} onChange={setDtCost} min={10_000} max={5_000_000} step={10_000} />
          <NumberField label="Defect cost (₹)" value={defCost} onChange={setDefCost} min={500} max={500_000} step={500} />
          <NumberField label="Deployment cost (₹)" value={depCost} onChange={setDepCost} min={100_000} max={100_000_000} step={100_000} />
        </div>

        <div className="grid grid-cols-4 gap-3 mt-5 max-lg:grid-cols-2">
          <KpiCard
            label="Annual Benefit"
            value={fmtInr(benefit)}
            hint={`${extraVehiclesYr.toFixed(0)} extra veh · ${defectsPreventedYr.toFixed(0)} fewer defects`}
          />
          <KpiCard label="Net Year-1" value={fmtInr(benefit - depCost)} accent={benefit - depCost >= 0 ? "#22c55e" : "#ef4444"} />
          <KpiCard
            label="ROI"
            value={`${roiPct.toLocaleString("en-IN", { maximumFractionDigits: 0 })}%`}
            delta={roiPct >= 0 ? `+${roiPct.toFixed(0)}%` : `${roiPct.toFixed(0)}%`}
            accent={roiPct >= 0 ? "#22c55e" : "#ef4444"}
          />
          <KpiCard
            label="Payback"
            value={Number.isFinite(paybackMonths) ? `${paybackMonths.toFixed(1)} mo` : "—"}
          />
        </div>
      </Panel>

      {/* Disclaimer — deliberately prominent, not a footnote */}
      <div
        className="rounded-lg border px-5 py-4 flex items-start gap-3"
        style={{
          borderColor: "#eab30888",
          background: "linear-gradient(90deg,#2a230d,#171d26 70%)",
        }}
      >
        <span className="text-lg leading-none mt-0.5">⚠️</span>
        <div>
          <div className="text-[13.5px] font-semibold text-amber-200">
            Illustrative prototype estimate — simulated numbers, not real industrial claims.
          </div>
          <div className="text-xs text-mut mt-1 leading-relaxed">
            &ldquo;Plant at a glance&rdquo; values are computed from the live simulated
            twin snapshot. The impact percentages (32% / 41% / 9%) are fixed,
            clearly-labeled planning assumptions — they are not measured outcomes.
            The ROI calculator simply propagates whatever assumptions you enter.
          </div>
        </div>
      </div>
    </div>
  );
}
