"use client";

import { useCallback, useState } from "react";

import {
  getTemporal,
  trackEvent,
  type TemporalFacts,
} from "../../../lib/api";

const INPUT =
  "rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";

const TOPICS = [
  ["overview", "Luận tổng quan"],
  ["career", "Công việc"],
  ["wealth", "Tài chính"],
  ["love", "Tình cảm"],
  ["health", "Sức khỏe"],
] as const;

const SCOPE_LABELS: Record<string, string> = {
  decadal: "Đại hạn",
  yearly: "Lưu niên",
  monthly: "Lưu nguyệt",
  daily: "Lưu nhật",
};

const ERROR_LABELS: Record<string, string> = {
  llm_unconfigured: "AI endpoint chưa được cấu hình — thử lại sau.",
  run_in_progress: "Luận giải đang chạy — đợi hoàn tất rồi thử lại.",
  grounding_failed: "Luận giải không đạt kiểm chứng — thử lại.",
  internal: "Lỗi máy chủ — thử lại sau.",
};

type Level = "decadal" | "yearly" | "monthly" | "daily";

interface EvidenceRef {
  id: string;
  kind: string;
  scope: string;
  entity_key: string;
  data: Record<string, unknown>;
}

const REF_RE = /\[E(\d{3})\]/g;

function FactBlock({ label, data }: { label: string; data: Record<string, unknown> | null }) {
  if (!data) return null;
  const mutagen = (data.mutagen as string[] | undefined) ?? [];
  const palace = (data.palace as string | undefined) ?? "";
  const name = (data.name as string | undefined) ?? "";
  return (
    <div className="rounded-lg border border-zinc-200 p-3 text-sm dark:border-zinc-700">
      <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-700">
        {label}
      </div>
      {(name || palace) && (
        <div className="mb-1 text-zinc-700 dark:text-zinc-300">
          {name} {palace && <span className="text-zinc-400">· {palace}</span>}
        </div>
      )}
      {mutagen.length > 0 && (
        <div className="text-xs text-zinc-500">
          Tứ hóa: {mutagen.join(" · ")}
        </div>
      )}
    </div>
  );
}

export function TimeNavigator({
  chartId,
  birthYear,
}: {
  chartId: string;
  birthYear: number;
}) {
  const now = new Date();
  const [level, setLevel] = useState<Level>("yearly");
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);
  const [day, setDay] = useState(now.getDate());

  const [facts, setFacts] = useState<TemporalFacts | null>(null);
  const [loadingFacts, setLoadingFacts] = useState(false);

  const [topic, setTopic] = useState<string>("overview");
  const [text, setText] = useState("");
  const [evidence, setEvidence] = useState<EvidenceRef[]>([]);
  const [openRefs, setOpenRefs] = useState<Set<string>>(new Set());
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">(
    "idle",
  );
  const [error, setError] = useState("");

  const loadFacts = useCallback(async () => {
    setLoadingFacts(true);
    setFacts(null);
    setText("");
    setEvidence([]);
    try {
      const q: { year?: number; month?: number; day?: number } = {};
      if (level !== "decadal") q.year = year;
      if (level === "monthly" || level === "daily") q.month = month;
      if (level === "daily") q.day = day;
      setFacts(await getTemporal(chartId, q));
      trackEvent("temporal_opened", { chartId, meta: { scope: level } });
    } catch (e) {
      setState("error");
      setError(e instanceof Error ? e.message : "Lỗi tải vận trình");
    } finally {
      setLoadingFacts(false);
    }
  }, [chartId, level, year, month, day]);

  const interpret = useCallback(async () => {
    setError("");
    setText("");
    setEvidence([]);
    setOpenRefs(new Set());
    let target: Record<string, unknown> | null = null;
    if (level === "yearly") target = { scope: "yearly", year };
    if (level === "monthly") target = { scope: "monthly", year, month };
    if (level === "daily") target = { scope: "daily", year, month, day };

    setState("streaming");
    trackEvent("interpret_started", { chartId, meta: { topic, level } });
    try {
      const resp = await fetch(`/api/charts/${chartId}/interpret`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, target }),
      });
      if (!resp.ok || !resp.body) {
        setState("error");
        setError(`API ${resp.status}`);
        return;
      }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = "";
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const frames = buf.split("\n\n");
        buf = frames.pop() ?? "";
        for (const frame of frames) {
          const ev = /event: (\w+)/.exec(frame)?.[1];
          const i = frame.indexOf("data: ");
          const data = i >= 0 ? frame.slice(i + 6) : undefined;
          if (!ev || !data) continue;
          const payload = JSON.parse(data);
          if (ev === "delta") setText((x) => x + payload);
          else if (ev === "replace") setText(payload);
          else if (ev === "evidence") setEvidence(payload.items);
          else if (ev === "done") {
            trackEvent("interpret_completed", {
              chartId,
              meta: { topic, level },
            });
          } else if (ev === "error") {
            setState("error");
            setError(ERROR_LABELS[payload.type] ?? ERROR_LABELS.internal);
            return;
          }
        }
      }
      setState("done");
    } catch {
      setState("error");
      setError(ERROR_LABELS.internal);
    }
  }, [chartId, level, year, month, day, topic]);

  const toggleRef = (id: string) =>
    setOpenRefs((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id);
      else n.add(id);
      return n;
    });

  const renderText = () => {
    const parts: React.ReactNode[] = [];
    let last = 0;
    for (const m of text.matchAll(REF_RE)) {
      const idx = m.index ?? 0;
      parts.push(text.slice(last, idx));
      const id = `E${m[1]}`;
      parts.push(
        <button
          key={`${id}-${idx}`}
          onClick={() => toggleRef(id)}
          className="rounded bg-amber-100 px-1 font-mono text-[11px] text-amber-800 hover:bg-amber-200 dark:bg-amber-900/40 dark:text-amber-300"
        >
          [{id}]
        </button>,
      );
      last = idx + m[0].length;
    }
    parts.push(text.slice(last));
    return parts;
  };

  const years = Array.from(
    { length: 15 },
    (_, i) => now.getFullYear() - 5 + i,
  ).filter((y) => y > birthYear);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <select
          className={INPUT}
          value={level}
          onChange={(e) => {
            setLevel(e.target.value as Level);
            setFacts(null);
            setText("");
          }}
        >
          <option value="decadal">Đại hạn</option>
          <option value="yearly">Lưu niên</option>
          <option value="monthly">Lưu nguyệt</option>
          <option value="daily">Lưu nhật</option>
        </select>
        {level !== "decadal" && (
          <select
            className={INPUT}
            value={year}
            onChange={(e) => setYear(Number(e.target.value))}
          >
            {years.map((y) => (
              <option key={y} value={y}>
                {y}
              </option>
            ))}
          </select>
        )}
        {(level === "monthly" || level === "daily") && (
          <select
            className={INPUT}
            value={month}
            onChange={(e) => setMonth(Number(e.target.value))}
          >
            {Array.from({ length: 12 }, (_, i) => i + 1).map((m) => (
              <option key={m} value={m}>
                Tháng {m}
              </option>
            ))}
          </select>
        )}
        {level === "daily" && (
          <select
            className={INPUT}
            value={day}
            onChange={(e) => setDay(Number(e.target.value))}
          >
            {Array.from({ length: 31 }, (_, i) => i + 1).map((d) => (
              <option key={d} value={d}>
                Ngày {d}
              </option>
            ))}
          </select>
        )}
        <button
          onClick={loadFacts}
          disabled={loadingFacts}
          className="rounded bg-zinc-800 px-3 py-1.5 text-sm text-white hover:bg-zinc-700 disabled:opacity-50"
        >
          {loadingFacts ? "Đang tính…" : "Xem vận trình"}
        </button>
      </div>

      {facts && (
        <div className="space-y-2">
          <p className="text-xs text-zinc-500">
            Mốc tính: {facts.anchor} — tầng:{" "}
            {facts.scopesIncluded.map((s) => SCOPE_LABELS[s]).join(" → ")}
          </p>
          <FactBlock label={SCOPE_LABELS.decadal} data={facts.decadal} />
          <FactBlock label={SCOPE_LABELS.yearly} data={facts.yearly} />
          <FactBlock label={SCOPE_LABELS.monthly} data={facts.monthly} />
          <FactBlock label={SCOPE_LABELS.daily} data={facts.daily} />

          {level !== "decadal" && (
            <div className="border-t border-zinc-200 pt-3 dark:border-zinc-700">
              <div className="mb-2 flex flex-wrap gap-2">
                {TOPICS.map(([t, label]) => (
                  <button
                    key={t}
                    onClick={() => setTopic(t)}
                    className={`rounded border px-2.5 py-1 text-xs ${
                      topic === t
                        ? "border-amber-600 bg-amber-50 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
                        : "border-zinc-300 text-zinc-600 dark:border-zinc-700"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <button
                  onClick={interpret}
                  disabled={state === "streaming"}
                  className="rounded bg-amber-600 px-3 py-1 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50"
                >
                  {state === "streaming" ? "Đang luận…" : "Luận bằng AI"}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {state === "error" && error && (
        <p className="text-sm text-red-600">{error}</p>
      )}

      {text && (
        <div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
          <div className="whitespace-pre-wrap text-sm leading-6">
            {renderText()}
          </div>
          {state === "streaming" && (
            <span className="mt-1 inline-block h-3 w-1.5 animate-pulse bg-amber-600" />
          )}
        </div>
      )}

      {evidence.length > 0 && openRefs.size > 0 && (
        <div className="space-y-1">
          {evidence
            .filter((e) => openRefs.has(e.id))
            .map((e) => (
              <div
                key={e.id}
                className="rounded border border-zinc-200 bg-zinc-50 p-2 font-mono text-[11px] dark:border-zinc-700 dark:bg-zinc-900"
              >
                <span className="text-amber-700">[{e.id}]</span>{" "}
                {e.entity_key} · {e.scope}
                <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap text-zinc-600 dark:text-zinc-400">
                  {JSON.stringify(e.data, null, 1)}
                </pre>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
