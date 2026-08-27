"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { SPEEDS } from "@/lib/constants";
import { useMemo } from "react";
import { useTwinStore } from "@/store/useTwinStore";
import type { StationMetric } from "@/lib/types";

function useRefetchInterval() {
  const speed = useTwinStore((s) => s.speed);
  return SPEEDS[speed] ?? false;
}

export function useMeta() {
  const interval = useRefetchInterval();
  return useQuery({ queryKey: ["meta"], queryFn: api.meta, refetchInterval: interval });
}

export function useStations() {
  return useQuery({ queryKey: ["stations"], queryFn: api.stations, staleTime: Infinity });
}

export function useLatestMetrics() {
  const interval = useRefetchInterval();
  return useQuery({
    queryKey: ["metrics-latest"],
    queryFn: api.latestMetrics,
    refetchInterval: interval,
  });
}

/** metrics keyed by station_id */
export function useMetricsByStation() {
  const { data, ...rest } = useLatestMetrics();
  const byStation = useMemo(() => {
    const m = new Map<string, StationMetric>();
    for (const r of data ?? []) m.set(r.station_id, r);
    return m;
  }, [data]);
  return { data: byStation, raw: data as StationMetric[] | undefined, ...rest };
}

export function useHistory(hours: number) {
  const interval = useRefetchInterval();
  return useQuery({
    queryKey: ["history", hours],
    queryFn: () => api.metricHistory(hours),
    refetchInterval: interval,
  });
}

export function useAlerts() {
  const interval = useRefetchInterval();
  return useQuery({ queryKey: ["alerts"], queryFn: api.alerts, refetchInterval: interval });
}

export function useDefects() {
  return useQuery({ queryKey: ["defects"], queryFn: api.defects });
}

export function useRecommendations() {
  return useQuery({ queryKey: ["recs"], queryFn: api.recommendations });
}

export function useScenarios() {
  return useQuery({
    queryKey: ["scenarios"],
    queryFn: api.scenarios,
    staleTime: Infinity,
  });
}

export function useConfidenceCurve() {
  return useQuery({
    queryKey: ["confidence-curve"],
    queryFn: api.confidenceCurve,
    staleTime: Infinity,
  });
}

export function useStationTelemetry(stationId: string | null) {
  const interval = useRefetchInterval();
  return useQuery({
    queryKey: ["telemetry", stationId],
    queryFn: () => api.stationTelemetry(stationId!),
    enabled: !!stationId,
    refetchInterval: interval,
  });
}

export function useWhatifMutation() {
  return useMutation({
    mutationFn: ({ stationId, actionKey }: { stationId: string; actionKey: string }) =>
      api.whatif(stationId, actionKey),
  });
}

export function useInjectScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (scenarioKey: string) => api.injectScenario(scenarioKey),
    onSuccess: () =>
      qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "stations" }),
  });
}

export function useResetSimulation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.resetSimulation(),
    onSuccess: () => qc.invalidateQueries(),
  });
}
