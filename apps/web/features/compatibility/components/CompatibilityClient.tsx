"use client";

import { useCallback, useState } from "react";

interface EvidenceRef {
  id: string;
  kind: string;
  source: string;
  scope: string;
  palace_key: string;
  entity_key: string;
  data: Record<string, unknown>;
}

const REF_RE = /\[E(\d{3})\]/g;

const INPUT =
  "w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";
const LABEL = "text-xs font-medium text-zinc-600 dark:text-zinc-400";

type TargetScope = "none" | "yearly" | "monthly" | "daily";

/** Accept `cs_…`, a `/chart/cs_…` URL, or a share link `/s/<token>` (resolved). */
async function resolveChartRef(raw: string): Promise<string | null> {
  const value = raw.trim();
  if (!value) return null;
  const direct = /(?:^|\/)?(cs_[A-Za-z0-9]+)/.exec(value);
  if (/\/s\//.test(value)) {
    const token = /\/s\/([A-Za-z0-9_-]+)/.exec(value)?.[1];
    if (!token) return null;
    const res = await fetch(`/s/${token}`, { cache: "no-store" });
    if (!res.ok) return null;
    const body = (await res.json()) as { id?: string };
    return body.id ?? null;
  }
  return direct?.[1] ?? null;
}

const ERROR_LABELS: Record<string, string> = {
  llm_unconfigured: "AI endpoint chưa được cấu hình — thử lại sau.",
  run_in_progress:
    "Luận giải cho cặp này đang chạy — vui lòng đợi hoàn tất rồi thử lại.",
  self_pair: "Hai lá số phải khác nhau.",
  grounding_failed: "Luận giải không đạt kiểm chứng — thử lại.",
  internal: "Lỗi máy chủ — thử lại sau.",
};

export function CompatibilityClient({
  initialA,
  initialB,
}: {
  initialA: string;
  initialB: string;
}) {
  const [inputA, setInputA] = useState(initialA);
  const [inputB, setInputB] = useState(initialB);
  const [scope, setScope] = useState<TargetScope>("none");
  const [year, setYear] = useState("");
  const [month, setMonth] = useState("");
  const [day, setDay] = useState("");

  const [text, setText] = useState("");
  const [evidence, setEvidence] = useState<EvidenceRef[]>([]);
  const [openRefs, setOpenRefs] = useState<Set<string>>(new Set());
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">(
    "idle",
  );
  const [error, setError] = useState("");

  const toggleRef = (id: string) =>
    setOpenRefs((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const start = useCallback(async () => {
    setError("");
    setText("");
    setEvidence([]);
    setOpenRefs(new Set());
    const [a, b] = await Promise.all([
      resolveChartRef(inputA),
      resolveChartRef(inputB),
    ]);
    if (!a || !b) {
      setState("error");
      setError(
        "Không đọc được mã lá số — dán mã `cs_…` hoặc URL trang lá số.",
      );
      return;
    }
    if (a === b) {
      setState("error");
      setError(ERROR_LABELS.self_pair);
      return;
    }
    let target: Record<string, unknown> | null = null;
    if (scope !== "none") {
      const y = Number(year);
      if (!y) {
        setState("error");
        setError("Nhập năm mục tiêu.");
        return;
      }
      target = { scope, year: y };
      if (scope !== "yearly") target.month = Number(month) || undefined;
      if (scope === "daily") target.day = Number(day) || undefined;
    }

    setState("streaming");
    try {
      const resp = await fetch("/api/compatibility", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chart_a_id: a, chart_b_id: b, target }),
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
          const dataIdx = frame.indexOf("data: ");
          const data = dataIdx >= 0 ? frame.slice(dataIdx + 6) : undefined;
          if (!ev || !data) continue;
          const payload = JSON.parse(data);
          if (ev === "delta") setText((x) => x + payload);
          else if (ev === "replace") setText(payload);
          else if (ev === "evidence") setEvidence(payload.items);
          else if (ev === "done") setState("done");
          else if (ev === "error") {
            setState("error");
            setError(
              ERROR_LABELS[payload.type as string] ??
                `Lỗi: ${payload.type ?? "error"}`,
            );
          }
        }
      }
      setState((s) => (s === "streaming" ? "error" : s));
      setError(
        (s) => s || "Luồng luận giải kết thúc trước khi hoàn tất.",
      );
    } catch (e) {
      setState("error");
      setError(String(e));
    }
  }, [inputA, inputB, scope, year, month, day]);

  const renderText = () => {
    const parts = text.split(REF_RE);
    const out = [];
    for (let i = 0; i < parts.length; i++) {
      if (i % 2 === 1) {
        const id = `E${parts[i]}`;
        const item = evidence.find((e) => e.id === id);
        out.push(
          <button
            key={i}
            onClick={() => toggleRef(id)}
            className="mx-0.5 rounded bg-amber-100 px-1 text-[10px] text-amber-800 hover:bg-amber-200"
            title={item ? `${item.kind} · ${item.scope}` : id}
          >
            Căn cứ {id}
          </button>,
        );
        if (openRefs.has(id) && item) {
          out.push(
            <span
              key={`${i}-d`}
              className="my-1 block rounded bg-zinc-50 p-2 text-[11px] text-zinc-600"
            >
              {id} · {item.kind} ·{" "}
              <span className="font-medium text-amber-800">{item.scope}</span>
              {item.entity_key ? ` · ${item.entity_key}` : ""}
              <span className="mt-1 block whitespace-pre-wrap font-mono text-[10px] text-zinc-500">
                {JSON.stringify(item.data)}
              </span>
            </span>,
          );
        }
      } else if (parts[i]) {
        out.push(<span key={i}>{parts[i]}</span>);
      }
    }
    return out;
  };

  return (
    <section className="rounded border border-zinc-200 p-4">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className={LABEL} htmlFor="chartA">
            Người A — mã lá số
          </label>
          <input
            id="chartA"
            value={inputA}
            onChange={(e) => setInputA(e.target.value)}
            placeholder="cs_… hoặc dán link /chart/… /s/…"
            className={INPUT}
          />
        </div>
        <div className="space-y-1">
          <label className={LABEL} htmlFor="chartB">
            Người B — mã lá số
          </label>
          <input
            id="chartB"
            value={inputB}
            onChange={(e) => setInputB(e.target.value)}
            placeholder="cs_… hoặc dán link /chart/… /s/…"
            className={INPUT}
          />
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className={LABEL} htmlFor="scope">
            Mục tiêu
          </label>
          <select
            id="scope"
            value={scope}
            onChange={(e) => setScope(e.target.value as TargetScope)}
            className={INPUT}
          >
            <option value="none">Bản mệnh (không thời hạn)</option>
            <option value="yearly">Theo năm</option>
            <option value="monthly">Theo tháng</option>
            <option value="daily">Theo ngày</option>
          </select>
        </div>
        {scope !== "none" && (
          <div className="space-y-1">
            <label className={LABEL} htmlFor="year">
              Năm
            </label>
            <input
              id="year"
              inputMode="numeric"
              value={year}
              onChange={(e) => setYear(e.target.value)}
              className={`${INPUT} w-24`}
              placeholder="2028"
            />
          </div>
        )}
        {(scope === "monthly" || scope === "daily") && (
          <div className="space-y-1">
            <label className={LABEL} htmlFor="month">
              Tháng
            </label>
            <input
              id="month"
              inputMode="numeric"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
              className={`${INPUT} w-20`}
              placeholder="3"
            />
          </div>
        )}
        {scope === "daily" && (
          <div className="space-y-1">
            <label className={LABEL} htmlFor="day">
              Ngày
            </label>
            <input
              id="day"
              inputMode="numeric"
              value={day}
              onChange={(e) => setDay(e.target.value)}
              className={`${INPUT} w-20`}
              placeholder="1"
            />
          </div>
        )}
        <button
          onClick={start}
          disabled={state === "streaming" || !inputA.trim() || !inputB.trim()}
          className="rounded bg-amber-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-amber-700 disabled:opacity-50"
        >
          Xu hợp bàn
        </button>
      </div>

      {state === "streaming" && (
        <p className="mt-3 text-xs text-zinc-400">Đang luận giải…</p>
      )}
      {error && (
        <p className="mt-3 rounded bg-rose-50 p-2 text-xs text-rose-700">
          {error}
        </p>
      )}
      {text && (
        <div className="mt-4 whitespace-pre-wrap text-sm leading-6 text-zinc-800">
          {renderText()}
        </div>
      )}
      {state === "done" && (
        <p className="mt-3 text-[10px] text-zinc-400">
          Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
        </p>
      )}
    </section>
  );
}
