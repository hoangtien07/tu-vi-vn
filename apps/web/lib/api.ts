const API_URL = process.env.API_INTERNAL_URL ?? "http://localhost:8000";

export interface ApiChartResponse {
  id: string;
  engine: string;
  engineVersion: string;
  engineProfileId: string;
  chartHash: string;
  shareToken?: string;
  chart: {
    schemaVersion: number;
    meta: Record<string, string>;
    chart: Record<string, unknown>;
  };
  patternHits: unknown[];
  createdAt: string;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...init });
  if (!res.ok) {
    const detail = (await res.json().catch(() => null)) as {
      detail?: unknown;
    } | null;
    const message =
      typeof detail?.detail === "string" ? detail.detail : `API ${res.status}`;
    const err = new Error(message);
    (err as { status?: number }).status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

export function getChart(id: string) {
  return apiFetch<ApiChartResponse>(`/api/charts/${id}`);
}

export function getSharedChart(token: string) {
  return apiFetch<ApiChartResponse>(`/s/${token}`);
}

export interface BirthPayload {
  calendar: "solar" | "lunar";
  date: string;
  time?: string;
  timeUnknown: boolean;
  gender: "male" | "female";
  placeName?: string;
  birthRegion?: "north" | "central" | "south";
  latitude?: number;
  longitude?: number;
  leapMonth: boolean;
  trueSolarTimeEnabled: boolean;
}

export function createChart(payload: BirthPayload) {
  return apiFetch<ApiChartResponse>("/api/charts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}
