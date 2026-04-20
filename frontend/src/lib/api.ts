import axios from "axios";

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
