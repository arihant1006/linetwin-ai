"use client";

import { useState } from "react";
import { Button, Select } from "./ui";
import {
  useInjectScenario,
  useMeta,
  useResetSimulation,
  useScenarios,
} from "@/hooks/useTwin";
import { SPEEDS } from "@/lib/constants";
import { useTwinStore } from "@/store/useTwinStore";

export function ScenarioSelector() {
  const { data: scenarios } = useScenarios();
  const { data: meta } = useMeta();
  const [picked, setPicked] = useState("");
  const inject = useInjectScenario();
  const reset = useResetSimulation();

  const active = meta?.active_scenario ?? "normal";
  const value = picked || active;
  const busy = inject.isPending || reset.isPending;

  return (
    <div className="flex items-center gap-2 min-w-0">
      <Select
        aria-label="Scenario"
        value={value}
        onChange={(e) => setPicked(e.target.value)}
        disabled={busy}
        className="max-w-[230px]"
      >
        {(scenarios ?? []).map((s) => (
          <option key={s.key} value={s.key}>
            {s.label}
          </option>
        ))}
      </Select>
      <Button
        onClick={() => inject.mutate(value)}
        disabled={busy || value === active}
        title={
          value === active
            ? "This scenario is already active"
            : "Re-simulates the live window under this failure and recomputes all twin artifacts"
        }
      >
        {inject.isPending ? "Injecting…" : "Inject Failure"}
      </Button>
      <Button variant="ghost" onClick={() => reset.mutate()} disabled={busy}>
        {reset.isPending ? "Resetting…" : "Reset Simulation"}
      </Button>
    </div>
  );
}

export function ScenarioStatus({ description }: { description?: boolean }) {
  const { data: scenarios } = useScenarios();
  const { data: meta } = useMeta();
  if (!meta) return null;
  const scen = scenarios?.find((s) => s.key === meta.active_scenario);
  const isNormal = meta.active_scenario === "normal";
  return (
    <div
      className="rounded-lg border px-4 py-3 flex flex-wrap items-center gap-x-6 gap-y-1"
      style={{
        borderColor: isNormal ? "#22c55e44" : "#f9731666",
        background: isNormal ? "#22c55e0d" : "#f9731614",
      }}
    >
      <span className="panel-label">
        ACTIVE SCENARIO{" "}
        <b style={{ color: isNormal ? "#22c55e" : "#f97316" }}>
          {scen?.label ?? meta.active_scenario}
        </b>
      </span>
      {description && scen?.description && (
        <span className="text-xs text-mut">{scen.description}</span>
      )}
    </div>
  );
}

/** Overlay shown while the expensive backend re-simulation runs. */
export function ScenarioBusyOverlay({
  show,
  label,
}: {
  show: boolean;
  label?: string;
}) {
  if (!show) return null;
  return (
    <div className="fixed inset-0 z-50 bg-bg/80 backdrop-blur-sm flex items-center justify-center">
      <div className="card px-8 py-7 max-w-md text-center">
        <div className="mx-auto mb-4 h-8 w-8 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
        <div className="text-sm font-semibold">{label ?? "Re-simulating the plant…"}</div>
        <div className="text-xs text-mut mt-2">
          The twin is regenerating telemetry for the affected window and rerunning
          inference over all 40 stations. This is real work, not a spinner — it can
          take several seconds (a full reset takes up to a minute).
        </div>
      </div>
    </div>
  );
}

export function SimClock() {
  const { data: meta } = useMeta();
  const t = meta?.sim_clock;
  const time = t ? t.split(" ")[1] : "--:--:--";
  return (
    <span
      className="num text-[13px] text-mut inline-flex items-center gap-1.5"
      title={`Simulated plant time: ${t ?? "unknown"}`}
    >
      ⏱ <span className="text-txt">{time}</span>
    </span>
  );
}

export function LiveRefreshControl() {
  const speed = useTwinStore((s) => s.speed);
  const setSpeed = useTwinStore((s) => s.setSpeed);
  return (
    <div className="inline-flex items-center rounded-md border border-line overflow-hidden">
      {Object.keys(SPEEDS).map((k) => (
        <button
          key={k}
          onClick={() => setSpeed(k as "1x")}
          className={`num text-[11px] px-2 py-1 cursor-pointer transition-colors ${
            speed === k
              ? "bg-accent/20 text-accent"
              : "text-mut hover:text-txt"
          }`}
          title={SPEEDS[k] ? `Auto-refresh every ${SPEEDS[k]}ms` : "Auto-refresh off"}
        >
          {k}
        </button>
      ))}
    </div>
  );
}
