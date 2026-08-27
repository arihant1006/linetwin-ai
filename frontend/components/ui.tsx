"use client";

import type { ReactNode, SelectHTMLAttributes } from "react";

export function Panel({
  label,
  right,
  children,
  className = "",
}: {
  label?: string;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`card p-4 ${className}`}>
      {(label || right) && (
        <header className="mb-3 flex items-center justify-between gap-3">
          {label && <h2 className="panel-label">{label}</h2>}
          {right}
        </header>
      )}
      {children}
    </section>
  );
}

export function KpiCard({
  label,
  value,
  hint,
  delta,
  accent,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  delta?: string;
  accent?: string;
}) {
  const up = delta?.startsWith("+");
  const down = delta?.startsWith("-");
  return (
    <div className="card px-4 py-3 min-w-0">
      <div className="panel-label truncate">{label}</div>
      <div
        className="num text-[26px] leading-tight font-semibold mt-1 truncate"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </div>
      <div className="flex items-center gap-2 mt-0.5">
        {delta && (
          <span
            className="num text-xs font-medium"
            style={{ color: up ? "#22c55e" : down ? "#ef4444" : "#8b98ab" }}
          >
            {up ? "▲" : down ? "▼" : ""} {delta.replace(/^[+-]/, "")}
          </span>
        )}
        {hint && <span className="text-xs text-mut truncate">{hint}</span>}
      </div>
    </div>
  );
}

type ButtonProps = {
  children: ReactNode;
  onClick?: () => void;
  variant?: "primary" | "ghost" | "danger";
  disabled?: boolean;
  className?: string;
  title?: string;
};

export function Button({
  children,
  onClick,
  variant = "primary",
  disabled,
  className = "",
  title,
}: ButtonProps) {
  const base =
    "inline-flex items-center justify-center gap-2 rounded-md text-[13px] font-medium px-3 py-1.5 transition-colors disabled:opacity-45 disabled:cursor-not-allowed cursor-pointer";
  const styles = {
    primary:
      "bg-accent/15 text-accent border border-accent/40 hover:bg-accent/25",
    ghost: "bg-transparent text-mut border border-line hover:text-txt hover:border-line-strong",
    danger:
      "bg-critical/15 text-critical border border-critical/50 hover:bg-critical/25",
  } as const;
  return (
    <button
      className={`${base} ${styles[variant]} ${className}`}
      onClick={onClick}
      disabled={disabled}
      title={title}
    >
      {children}
    </button>
  );
}

export function Select({
  label,
  className = "",
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { label?: string }) {
  return (
    <label className="flex flex-col gap-1 min-w-0">
      {label && <span className="panel-label">{label}</span>}
      <select
        {...props}
        className={`bg-card-raised border border-line rounded-md text-[13px] px-2 py-1.5 text-txt outline-none focus:border-accent/60 cursor-pointer ${className}`}
      />
    </label>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-10 text-mut text-sm">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-line-strong border-t-accent" />
      {label ?? "Loading…"}
    </div>
  );
}

export function ErrorNote({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div className="card border-critical/40 p-4 my-4 text-sm text-mut">
      <b className="text-critical">API unreachable.</b> Start the backend with{" "}
      <code className="num text-txt">.venv/bin/uvicorn server.main:app --port 8000</code>{" "}
      <span className="block mt-1 opacity-70">({msg})</span>
    </div>
  );
}

export function SimOnlyBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-bold tracking-wider bg-slate-500/20 text-slate-300 border border-slate-400/30">
      SIM ONLY
    </span>
  );
}
