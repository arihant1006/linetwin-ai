"use client";

import { useSyncExternalStore, type ReactNode } from "react";

const emptySubscribe = () => () => {};

/**
 * Defers rendering until after mount. Browser extensions (e.g. BitDefender)
 * inject attributes like bis_skin_checked into every element before React
 * hydrates, causing unavoidable hydration mismatches; gating on mount makes
 * the app immune regardless of what the client environment injects.
 */
export function ClientOnly({ children }: { children: ReactNode }) {
  // Server snapshot = false, client snapshot = true → renders nothing during
  // SSR/hydration and children after mount, without an effect-driven setState.
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
  // Dark shell matches --bg so there is no white flash while mounting.
  return mounted ? (
    <>{children}</>
  ) : (
    <div style={{ minHeight: "100dvh", background: "#0e1117" }} />
  );
}
