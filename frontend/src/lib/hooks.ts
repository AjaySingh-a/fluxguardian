import { useMutation, useQuery } from "@tanstack/react-query";
import {
  analyzeDiff,
  generateReport,
  getGovernancePulse,
  getLineage,
  getRecentAnalyses,
} from "@/lib/api";
import type { BlastRadiusReport } from "@/types/api";

export function useRecentAnalyses() {
  return useQuery({
    queryKey: ["pr", "recent"],
    queryFn: getRecentAnalyses,
    staleTime: 30_000,
    retry: 1,
  });
}

export function useGovernancePulse() {
  return useQuery({
    queryKey: ["governance", "pulse"],
    queryFn: getGovernancePulse,
    staleTime: 60_000,
    retry: 1,
  });
}

export function useLineage(fqn: string) {
  return useQuery({
    queryKey: ["lineage", fqn],
    queryFn: () => getLineage(fqn),
    enabled: Boolean(fqn),
    staleTime: 60_000,
    retry: 1,
  });
}

export function useAnalyzeDiff() {
  return useMutation({
    mutationFn: (diff: string) => analyzeDiff(diff),
  });
}

export function useGenerateReport() {
  return useMutation({
    mutationFn: (report: BlastRadiusReport) => generateReport(report),
  });
}
