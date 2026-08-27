"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { LiveRefreshControl, ScenarioBusyOverlay, ScenarioSelector, SimClock } from "@/components/Controls";
import { useInjectScenario, useResetSimulation } from "@/hooks/useTwin";

const PERSONAS = [
  { slug: "supervisor", label: "Floor Supervisor" },
  { slug: "manager", label: "Plant Manager" },
  { slug: "leadership", label: "Leadership" },
  { slug: "whatif", label: "What-If Simulator" },
] as const;

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const inject = useInjectScenario();
  const reset = useResetSimulation();

  return (
    <div className="min-h-screen flex flex-col">
      <header className="sticky top-0 z-40 border-b border-line bg-bg/90 backdrop-blur">
        <div className="mx-auto max-w-[1600px] px-4 h-14 flex items-center gap-4">
          <Link href="/" className="flex items-center gap-2 shrink-0 group">
            <span className="h-2.5 w-2.5 rounded-full bg-accent shadow-[0_0_10px_#22d3ee]" />
            <span className="font-bold tracking-tight text-[15px] group-hover:text-accent transition-colors">
              LineTwin<span className="text-accent">.ai</span>
            </span>
          </Link>

          <nav className="flex items-center gap-1 min-w-0 overflow-x-auto">
            {PERSONAS.map((p) => {
              const active = pathname === `/dashboard/${p.slug}`;
              return (
                <Link
                  key={p.slug}
                  href={`/dashboard/${p.slug}`}
                  className={`whitespace-nowrap rounded-md px-3 py-1.5 text-[13px] font-medium transition-colors ${
                    active
                      ? "bg-accent/15 text-accent"
                      : "text-mut hover:text-txt hover:bg-card-raised"
                  }`}
                >
                  {p.label}
                </Link>
              );
            })}
          </nav>

          <div className="ml-auto flex items-center gap-3 shrink-0">
            <SimClock />
            <LiveRefreshControl />
            <ScenarioSelector />
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5">{children}</main>

      <footer className="border-t border-line py-3">
        <div className="mx-auto max-w-[1600px] px-4 flex items-center justify-between gap-4 text-[11px] text-mut">
          <span>
            Simulation-only prototype · seeded deterministic data (seed 42) · no
            connection to any real plant system
          </span>
          <span>
            All recommendations are <b className="text-slate-300">SIM ONLY</b>;
            PLC writes are impossible by design.
          </span>
        </div>
      </footer>

      <ScenarioBusyOverlay show={inject.isPending} label={`Injecting failure scenario…`} />
      <ScenarioBusyOverlay
        show={reset.isPending}
        label="Resetting to normal production — regenerating the full 7-day history…"
      />
    </div>
  );
}
