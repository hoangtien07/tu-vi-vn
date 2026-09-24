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

export interface ApiProfile {
  id: string;
  displayName: string;
  relationship: string | null;
  chartId: string;
  visibility: string;
}

export function listProfiles() {
  return apiFetch<ApiProfile[]>("/api/profiles");
}

export function createProfile(body: {
  display_name: string;
  relationship?: string;
  chart_id: string;
}) {
  return apiFetch<ApiProfile>("/api/profiles", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function deleteProfile(id: string) {
  return apiFetch<void>(`/api/profiles/${id}`, { method: "DELETE" });
}

export interface TemporalFacts {
  chartId: string;
  anchor: string;
  decadal: Record<string, unknown> | null;
  yearly: Record<string, unknown> | null;
  monthly: Record<string, unknown> | null;
  daily: Record<string, unknown> | null;
  scopesIncluded: string[];
}

export function getTemporal(
  chartId: string,
  q: { year?: number; month?: number; day?: number },
) {
  const params = new URLSearchParams();
  if (q.year) params.set("year", String(q.year));
  if (q.month) params.set("month", String(q.month));
  if (q.day) params.set("day", String(q.day));
  return apiFetch<TemporalFacts>(
    `/api/charts/${chartId}/temporal?${params.toString()}`,
  );
}

export interface ReadingRow {
  id: string;
  topic: string;
  status: string;
  isCompatibility: boolean;
  targetDate: string | null;
  createdAt: string;
}

export function getReadings(chartId: string) {
  return apiFetch<ReadingRow[]>(`/api/charts/${chartId}/readings`);
}
