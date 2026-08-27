"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useState } from "react";
import { motion } from "framer-motion";

const TwinScene = dynamic(() => import("@/components/landing/TwinScene"), {
  ssr: false,
});

function useScrollProgress() {
  const [p, setP] = useState(0);
  useEffect(() => {
    function onScroll() {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setP(max > 0 ? window.scrollY / max : 0);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return p;
}

const STAGES = [
  {
    id: "hero",
    range: [0, 0.2],
    kicker: "LineTwin.ai · Accenture Innovation Challenge 2026",
    title: "The line keeps working.\nEven where you can't see it.",
    body: "A local, simulation-only digital twin that infers station health and bottlenecks across a 40-station automotive assembly line — including where sensors are missing or dark.",
  },
  {
    id: "observe",
    range: [0.2, 0.46],
    kicker: "LAYER 01 — OBSERVE",
    title: "Real lines are never\nuniformly instrumented.",
    body: "40% of stations have rich telemetry, 35% medium, 25% sparse. A dying sensor on a degrading machine can make that station look healthier, not worse — silence reads as \u201cnothing to report\u201d.",
  },
  {
    id: "infer",
    range: [0.46, 0.68],
    kicker: "LAYER 02 — INFER",
    title: "When it can't see directly,\nit reads the flow around it.",
    body: "Multi-causal, intermittent root causes rarely show up as one clean signal. The twin fuses upstream queue build-up, downstream starvation, neighbor health and manual checklists into every score — and says exactly how sure it is. Defects created early surface late, so root-cause tracing looks backward through time and through the line.",
  },
  {
    id: "recommend",
    range: [0.68, 0.86],
    kicker: "LAYER 03 — RECOMMEND",
    title: "One model.\nFour ways to act on it.",
    body: "A floor supervisor mid-shift, a plant manager planning next week and leadership weighing an investment need three different lenses on the same underlying model — not three separate products. Every recommendation carries its evidence chain and confidence.",
  },
  {
    id: "simulate",
    range: [0.86, 1.01],
    kicker: "LAYER 04 — SIMULATE (CONTROL IS DELIBERATELY IMPOSSIBLE)",
    title: "Decision support,\nnot a control system — by design.",
    body: "What-if projections show the before/after of an action before anyone takes it. And when anything tries to write to the plant, PLCAdapter.write() raises RuntimeError. That dead end is a design choice, proven live in the product.",
  },
] as const;

export default function LandingPage() {
  const p = useScrollProgress();

  return (
    <div className="relative">
      <TwinScene />

      {/* readability scrim over the 3D scene (left-weighted) */}
      <div
        className="pointer-events-none fixed inset-0 z-[5]"
        style={{
          background:
            "linear-gradient(90deg, rgba(10,13,18,.92) 0%, rgba(10,13,18,.78) 34%, rgba(10,13,18,.25) 60%, transparent 80%)",
        }}
      />

      {/* progress rail */}
      <div className="fixed right-6 top-1/2 -translate-y-1/2 z-30 flex flex-col gap-2">
        {STAGES.map((s) => {
          const active = p >= s.range[0] && p < s.range[1];
          return (
            <span
              key={s.id}
              className="rounded-full transition-all duration-500 ease-out"
              style={{
                width: active ? 22 : 8,
                height: 4,
                background: active ? "#22d3ee" : "#33415c",
                boxShadow: active ? "0 0 8px #22d3ee88" : undefined,
              }}
            />
          );
        })}
      </div>

      <div className="relative z-10">
        {STAGES.map((s, idx) => (
          <section
            key={s.id}
            className="min-h-screen flex items-center px-[7vw]"
          >
            <motion.div
              initial={{ opacity: 0, y: 36 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ amount: 0.45 }}
              transition={{ duration: 0.7, ease: [0.22, 0.61, 0.36, 1] }}
              className={`max-w-xl pointer-events-none rounded-2xl border border-line/50 bg-bg-deep/70 backdrop-blur-sm p-8 -ml-2 md:p-10 shadow-[0_8px_40px_rgba(5,8,12,.55)] ${
                s.id === "hero" ? "" : ""
              }`}
            >
              <div className="panel-label !text-accent mb-3">{s.kicker}</div>
              <h1
                className={`font-bold tracking-tight whitespace-pre-line ${
                  s.id === "hero"
                    ? "text-4xl md:text-5xl leading-[1.08]"
                    : "text-3xl md:text-4xl leading-tight"
                }`}
              >
                {s.title}
              </h1>
              <p className="mt-5 text-mut text-[15px] leading-relaxed">
                {s.body}
              </p>

              {s.id === "hero" && (
                <div className="mt-8 flex items-center gap-3 pointer-events-auto flex-wrap">
                  <Link
                    href="/dashboard/supervisor"
                    className="rounded-md bg-accent/15 border border-accent/50 text-accent px-5 py-2.5 text-sm font-semibold hover:bg-accent/25 transition-colors"
                  >
                    Enter the dashboards →
                  </Link>
                  <Link
                    href="/dashboard/whatif"
                    className="rounded-md border border-line px-5 py-2.5 text-sm font-medium text-mut hover:text-txt transition-colors"
                  >
                    See the PLC safety proof
                  </Link>
                </div>
              )}

              {idx === 0 && (
                <div className="mt-10 flex items-center gap-2 text-mut text-xs pointer-events-none">
                  <motion.span
                    animate={{ y: [0, 6, 0] }}
                    transition={{ repeat: Infinity, duration: 1.6, ease: "easeInOut" }}
                    className="inline-block"
                  >
                    ↓
                  </motion.span>
                  Scroll — the twin walks the line
                </div>
              )}
            </motion.div>
          </section>
        ))}

        <footer className="relative z-10 border-t border-line/60 bg-bg/80 backdrop-blur py-6 px-[7vw] flex flex-wrap items-center justify-between gap-3 text-xs text-mut">
          <span>
            Simulation-only prototype · deterministic seeded data · runs fully
            local, no external services
          </span>
          <span className="flex gap-4">
            <Link href="/dashboard/supervisor" className="hover:text-txt">Floor Supervisor</Link>
            <Link href="/dashboard/manager" className="hover:text-txt">Plant Manager</Link>
            <Link href="/dashboard/leadership" className="hover:text-txt">Leadership</Link>
            <Link href="/dashboard/whatif" className="hover:text-txt">What-If</Link>
          </span>
        </footer>
      </div>
    </div>
  );
}
