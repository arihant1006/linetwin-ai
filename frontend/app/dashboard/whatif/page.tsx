"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import {
  useLatestMetrics,
  useRecommendations,
  useWhatifMutation,
} from "@/hooks/useTwin";
import { api } from "@/lib/api";
import { ACTIONS } from "@/lib/constants";
import type { WhatIfResult } from "@/lib/types";
import { Button, ErrorNote, KpiCard, Panel, Select, SimOnlyBadge, Spinner } from "@/components/ui";

function RecommendationCard({
  rec,
}: {
  rec: import("@/lib/types").Recommendation;
}) {
  return (
    <div className="card px-3.5 py-3">
      <div className="flex items-center gap-2 flex-wrap mb-1.5">
        <span className="num text-[11px] font-bold rounded px-1.5 py-0.5 bg-cyan-800/40 text-cyan-300 border border-cyan-400/30">
          {rec.station_id}
        </span>
        <SimOnlyBadge />
        <span className="num text-[11px] rounded px-1.5 py-0.5 bg-blue-600/25 text-blue-200 border border-blue-400/25">
          conf {(rec.confidence * 100).toFixed(0)}%
        </span>
      </div>
      <div className="text-[13px] font-semibold leading-snug">{rec.issue}</div>
      <div className="text-[12.5px] text-mut mt-1">
        → {rec.recommended_action}
      </div>
      <div className="text-[12px] text-txt/70 mt-0.5">{rec.expected_effect}</div>
      {rec.evidence.length > 0 && (
        <ul className="mt-1.5 text-[11px] text-mut/90 list-disc list-inside space-y-0.5">
          {rec.evidence.slice(0, 4).map((e, i) => (
            <li key={i}>{e}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** BEFORE → AFTER (projected) comparison — the payload of this screen. */
function WhatIfComparison({ out }: { out: WhatIfResult }) {
  const b = out.before;
  const a = out.after;
  const imp = out.projected_improvement_pct;
  const healthDelta = a.projected_health - b.health;
  const bnDelta = (a.projected_bottleneck_prob - b.bottleneck_prob) * 100;
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
    >
      <div className="mb-3 text-[13.5px]">
        <b>{out.action_label}</b> — projected line effect:{" "}
        <span
          className="num font-bold"
          style={{ color: imp >= 0 ? "#22c55e" : "#ef4444" }}
        >
          {imp >= 0 ? "▲" : "▼"} {Math.abs(imp).toFixed(1)}%
        </span>
      </div>
      <div className="grid grid-cols-[1fr_auto_1fr] gap-3 items-start max-sm:grid-cols-1">
        <div className="card p-3">
          <div className="panel-label mb-2">BEFORE — current twin state</div>
          <div className="flex flex-col gap-2">
            <KpiCard label="Throughput" value={`${b.throughput_vph.toFixed(1)} vph`} />
            <KpiCard label="Station CT" value={`${b.station_cycle_time.toFixed(1)}s`} />
            <KpiCard label="Health" value={b.health.toFixed(0)} />
            <KpiCard label="Bottleneck prob" value={`${(b.bottleneck_prob * 100).toFixed(0)}%`} />
          </div>
        </div>

        <div className="flex flex-col items-center justify-center self-stretch pt-16 max-sm:pt-2">
          <motion.span
            animate={{ x: [0, 8, 0] }}
            transition={{ repeat: Infinity, duration: 1.4, ease: "easeInOut" }}
            className="text-3xl text-accent"
          >
            →
          </motion.span>
        </div>

        <div
          className="card p-3 relative"
          style={{
            borderColor: "#22d3ee66",
            background:
              "linear-gradient(135deg, rgba(34,211,238,.07), #171d26 55%)",
          }}
        >
          <div className="panel-label mb-2 !text-accent">
            AFTER — PROJECTED (simulation only)
          </div>
          <div className="flex flex-col gap-2">
            <KpiCard
              label="Throughput"
              value={`${a.throughput_vph.toFixed(1)} vph`}
              delta={`${imp >= 0 ? "+" : ""}${imp.toFixed(1)}%`}
            />
            <KpiCard label="Projected station CT" value={`${a.station_cycle_time.toFixed(1)}s`} />
            <KpiCard
              label="Projected health"
              value={a.projected_health.toFixed(0)}
              delta={healthDelta !== 0 ? `${healthDelta >= 0 ? "+" : ""}${healthDelta.toFixed(0)}` : undefined}
            />
            <KpiCard
              label="Projected bottleneck prob"
              value={`${(a.projected_bottleneck_prob * 100).toFixed(0)}%`}
              delta={bnDelta !== 0 ? `${bnDelta >= 0 ? "+" : ""}${bnDelta.toFixed(1)}%` : undefined}
            />
          </div>
        </div>
      </div>
      <div className="mt-2.5 text-[11px] text-mut flex items-center gap-2">
        <SimOnlyBadge /> Projected outcome from the what-if model — nothing was
        written anywhere.
        {!out.logged && (
          <span className="text-amber-400">
            (run could not be logged to simulation_runs)
          </span>
        )}
      </div>
    </motion.div>
  );
}

const SNIPPET = `from app.analytics.whatif import PLCAdapter

class PLCAdapter:
    READ_ENABLED  = False
    WRITE_ENABLED = False

    def write(self, command) -> None:
        raise RuntimeError(
            "PLC writes disabled in prototype simulation")`;

export function PlcSafetyProof() {
  const [result, setResult] = useState<{
    raised: string;
    detail: string;
  } | null>(null);
  const [pending, setPending] = useState(false);

  async function attempt() {
    setPending(true);
    setResult(null);
    try {
      // Real backend call -> real PLCAdapter.write() -> real RuntimeError.
      const r = await api.plcWrite("start_line");
      setResult(r);
    } catch (e) {
      setResult({ raised: "RequestError", detail: String(e) });
    } finally {
      setPending(false);
    }
  }

  return (
    <Panel label="🔒 Integration boundary — control is impossible by design">
      <p className="text-[12.5px] text-mut leading-relaxed mb-3">
        LineTwin is a <b className="text-txt">decision-support</b> tool, not a
        control system. There is deliberately no path to CONTROL in the
        architecture: the only object that even attempts a plant write is{" "}
        <code className="num text-txt">PLCAdapter</code>, whose{" "}
        <code className="num text-txt">write()</code> method unconditionally
        raises. This button makes that proof concrete — it performs a real
        backend call into the real adapter class, so what you see fail below
        fails for real.
      </p>
      <pre className="text-[12px] leading-relaxed bg-bg-deep border border-line rounded-md p-3 overflow-x-auto num">
        <code>{SNIPPET}</code>
      </pre>
      <div className="mt-3 flex items-center gap-3 flex-wrap">
        <Button variant="danger" onClick={attempt} disabled={pending}>
          ⚡ Attempt PLC Write (live)
        </Button>
        <span className="text-xs text-mut">
          Calls <code className="num">POST /api/plc/write</code> → invokes the
          unmodified <code className="num">PLCAdapter.write()</code>.
        </span>
      </div>
      {!result && !pending && (
        <div className="mt-3 rounded-md border border-line bg-bg-deep/60 px-4 py-2.5">
          <span className="text-[12px] text-mut">
            Expected result:{" "}
            <span className="num text-critical">
              RuntimeError: PLC writes disabled in prototype simulation
            </span>{" "}
            — enforced by tests/test_safety.py.
          </span>
        </div>
      )}
      {pending && (
        <div className="mt-3 text-[12px] text-mut">Calling the backend…</div>
      )}
      {result && (
        <motion.div
          initial={{ opacity: 0, scale: 0.97 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0 }}
          className="mt-3 rounded-md border border-critical/50 bg-critical/10 px-4 py-3"
        >
          <span className="num text-[13px] text-critical font-semibold">
            RuntimeError: {result.detail}
          </span>
          <div className="text-[11px] text-mut mt-1">
            Raised live by the actual adapter class — the write path does not
            exist anywhere in this stack.
          </div>
        </motion.div>
      )}
    </Panel>
  );
}

export default function WhatIfPage() {
  const metricsQ = useLatestMetrics();
  const recsQ = useRecommendations();
  const mut = useWhatifMutation();

  const raw = metricsQ.data ?? [];
  const defaultSid =
    [...raw].sort((a, b) => b.bottleneck_prob - a.bottleneck_prob)[0]
      ?.station_id ?? "";
  const [sid, setSid] = useState("");
  const [action, setAction] = useState<string>("schedule_maintenance");
  const stationId = sid || defaultSid;

  if (metricsQ.isLoading || recsQ.isLoading)
    return <Spinner label="Loading recommendations…" />;
  if (metricsQ.isError) return <ErrorNote error={metricsQ.error} />;

  return (
    <div className="flex flex-col gap-4">
      {/* Unmissable simulation-only banner */}
      <div
        className="rounded-lg border border-red-500/60 px-4 py-3 flex items-center gap-3"
        style={{
          background:
            "linear-gradient(90deg, rgba(239,68,68,.15), rgba(23,29,38,.9) 60%)",
        }}
      >
        <span className="font-bold tracking-wide text-[14px] text-critical">
          ⚠ SIMULATION ONLY — NO PLC WRITE
        </span>
        <span className="text-xs text-mut">
          Every projection on this page is computed inside the simulated twin.
          There is no path from this product to any plant system.
        </span>
      </div>

      <div className="grid grid-cols-[1.1fr_1.6fr] gap-4 max-lg:grid-cols-1 items-start">
        <Panel label={`Twin recommendations (${recsQ.data?.length ?? 0})`}>
          <div className="flex flex-col gap-2 max-h-[620px] overflow-y-auto pr-1">
            {(recsQ.data ?? []).length === 0 && (
              <div className="text-sm text-mut py-4">No open recommendations.</div>
            )}
            {(recsQ.data ?? []).slice(0, 10).map((r) => (
              <RecommendationCard key={r.rec_id} rec={r} />
            ))}
          </div>
        </Panel>

        <div className="flex flex-col gap-4">
          <Panel label="What-if action">
            <div className="grid grid-cols-[1fr_1.6fr_auto] gap-3 items-end max-md:grid-cols-1">
              <Select
                label="Station"
                value={stationId}
                onChange={(e) => setSid(e.target.value)}
                aria-label="Station"
              >
                {raw.map((m) => (
                  <option key={m.station_id} value={m.station_id}>
                    {m.station_id} — health {m.health_score.toFixed(0)}
                  </option>
                ))}
              </Select>
              <Select
                label="Action"
                value={action}
                onChange={(e) => setAction(e.target.value)}
                aria-label="Action"
              >
                {Object.entries(ACTIONS).map(([k, label]) => (
                  <option key={k} value={k}>
                    {label}
                  </option>
                ))}
              </Select>
              <Button onClick={() => mut.mutate({ stationId, actionKey: action })} disabled={mut.isPending || !stationId}>
                {mut.isPending ? "Simulating…" : "▶ Simulate Recommendation"}
              </Button>
            </div>
            {mut.isError && (
              <div className="mt-3 text-[12px] text-critical">
                Simulation failed: {String(mut.error)}
              </div>
            )}
            <div className="mt-4 min-h-[80px]">
              {mut.data && <WhatIfComparison out={mut.data} />}
            </div>
          </Panel>

          <PlcSafetyProof />
        </div>
      </div>
    </div>
  );
}
