import axios from "axios";
import type {
  AnalysisCard,
  BlastRadiusReport,
  GovernancePulse,
  LineageGraph,
} from "@/types/api";

const baseURL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ??
  "http://localhost:8000";

export const api = axios.create({
  baseURL,
  timeout: 15_000,
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (import.meta.env.DEV) {
      console.error("[api] request failed", error);
    }
    return Promise.reject(error);
  },
);

export type HealthResponse = { status: string };
export type VersionResponse = { version: string };

export async function getHealth() {
  const { data } = await api.get<HealthResponse>("/health");
  return data;
}

export async function getVersion() {
  const { data } = await api.get<VersionResponse>("/version");
  return data;
}

export async function getRecentAnalyses(): Promise<AnalysisCard[]> {
  const { data } = await api.get<AnalysisCard[]>("/api/pr/recent");
  return data;
}

export async function getGovernancePulse(): Promise<GovernancePulse> {
  const { data } = await api.get<GovernancePulse>("/api/governance/pulse");
  return data;
}

export async function getLineage(fqn: string): Promise<LineageGraph> {
  const { data } = await api.get<LineageGraph>(`/api/assets/${fqn}/lineage`);
  return data;
}

export async function analyzeDiff(diffText: string): Promise<BlastRadiusReport[]> {
  const { data } = await api.post<BlastRadiusReport[]>("/api/analyze", {
    diff: diffText,
  });
  return data;
}
