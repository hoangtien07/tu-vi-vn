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
  // Server components fetch the API directly; in the browser the absolute
  // URL is both unreachable (internal host) and cross-origin — use the
  // same-origin /api/* rewrite instead.
  const serverSide = typeof window === "undefined";
  const url = serverSide ? `${API_URL}${path}` : path;
  const headers = new Headers(init?.headers);
  if (serverSide) {
    // Forward only our session cookie so SSR views reflect login state
    // (I15 merge view needs it). Client bundles drop this branch.
    const { cookies } = await import("next/headers");
    const token = (await cookies()).get("tv_session");
    if (token) headers.set("Cookie", `tv_session=${token.value}`);
  }
  const res = await fetch(url, { cache: "no-store", ...init, headers });
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
  if (res.status === 204) return undefined as T;
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

export interface ReadingDetail extends ReadingRow {
  outputText: string | null;
}

export function getReading(chartId: string, runId: string) {
  return apiFetch<ReadingDetail>(
    `/api/charts/${chartId}/readings/${runId}`,
  );
}

/** SPEC_V02 §7 — fire-and-forget product event; never throws. */
export function trackEvent(
  event: string,
  extra: { profileId?: string; chartId?: string; meta?: Record<string, unknown> } = {},
) {
  if (typeof window === "undefined") return;
  fetch("/api/events", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      event,
      clientEventId: `fe-${event}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ...extra,
    }),
  }).catch(() => {});
}

/** Server-side variant (server actions): posts directly to the API. */
export async function trackEventServer(
  event: string,
  extra: { profileId?: string; chartId?: string; meta?: Record<string, unknown> } = {},
) {
  try {
    await apiFetch("/api/events", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ event, ...extra }),
    });
  } catch {
    /* analytics never blocks UX */
  }
}

// ---------- v0.3 — Today / auth / chat ----------

export interface TodayHighlight {
  palace: string;
  topicHint: string;
  summary: string;
}

export interface TodayFacts {
  chartId: string;
  date: string;
  facts: Record<string, unknown>;
  highlights: TodayHighlight[];
}

export function getToday(chartId: string, date?: string) {
  const q = date ? `?date=${date}` : "";
  return apiFetch<TodayFacts>(`/api/charts/${chartId}/today${q}`);
}

export interface AuthUser {
  id: string;
  email: string;
}

export async function authRegister(email: string, password: string) {
  return apiFetch<AuthUser>("/api/auth/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function authLogin(email: string, password: string) {
  return apiFetch<AuthUser>("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export async function authLogout() {
  await fetch("/api/auth/logout", { method: "POST" });
}

export async function authMe(): Promise<AuthUser | null> {
  const res = await fetch("/api/auth/me", { cache: "no-store" });
  return res.ok ? ((await res.json()) as AuthUser) : null;
}

export interface ChatReply {
  conversationId: string;
  reply: string;
}

export interface ChatTarget {
  scope: "yearly" | "monthly" | "daily";
  year: number;
  month?: number;
  day?: number;
}

export async function sendChat(
  chartId: string,
  message: string,
  conversationId?: string,
  target?: ChatTarget,
): Promise<ChatReply> {
  const res = await fetch(`/api/charts/${chartId}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      message,
      conversation_id: conversationId,
      target,
    }),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return (await res.json()) as ChatReply;
}
