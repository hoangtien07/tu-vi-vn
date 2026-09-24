"use client";

import { useCallback, useState } from "react";

const TOPICS: { key: string; label: string }[] = [
  { key: "overview", label: "Tổng quan" },
  { key: "career", label: "Sự nghiệp" },
  { key: "wealth", label: "Tài vận" },
  { key: "love", label: "Tình duyên" },
  { key: "health", label: "Sức khỏe" },
];

interface EvidenceRef {
  id: string;
  kind: string;
  scope: string;
  palace_key: string;
  entity_key: string;
}

const REF_RE = /\[E(\d{3})\]/g;

export function InterpretPanel({ chartId }: { chartId: string }) {
  const [topic, setTopic] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [evidence, setEvidence] = useState<EvidenceRef[]>([]);
  const [openRefs, setOpenRefs] = useState<Set<string>>(new Set());
  const [state, setState] = useState<
    "idle" | "streaming" | "done" | "error"
  >("idle");
  const [error, setError] = useState("");

  const toggleRef = (id: string) =>
    setOpenRefs((s) => {
      const next = new Set(s);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });

  const start = useCallback(
    async (t: string) => {
      setTopic(t);
      setText("");
      setEvidence([]);
      setOpenRefs(new Set());
      setError("");
      setState("streaming");
      try {
        const resp = await fetch(`/api/charts/${chartId}/interpret`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ topic: t }),
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
            const data =
              dataIdx >= 0 ? frame.slice(dataIdx + 6) : undefined;
            if (!ev || !data) continue;
            const payload = JSON.parse(data);
            if (ev === "delta") setText((x) => x + payload);
            else if (ev === "evidence") setEvidence(payload.items);
            else if (ev === "done") setState("done");
            else if (ev === "error") {
              setState("error");
              setError(payload.type ?? "error");
            }
          }
        }
        setState((s) => (s === "streaming" ? "done" : s));
      } catch (e) {
        setState("error");
        setError(String(e));
      }
    },
    [chartId],
  );

  // Render text with [E###] → clickable "Căn cứ" chips
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
              {id} · {item.kind} · {item.scope}
              {item.entity_key ? ` · ${item.entity_key}` : ""}
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
    <section className="mt-6 rounded border border-zinc-200 p-4">
      <h2 className="mb-3 text-sm font-semibold">Luận giải</h2>
      <div className="mb-3 flex flex-wrap gap-2">
        {TOPICS.map((t) => (
          <button
            key={t.key}
            onClick={() => start(t.key)}
            disabled={state === "streaming"}
            className={`rounded border px-3 py-1 text-xs ${
              topic === t.key
                ? "border-amber-600 bg-amber-50 text-amber-800"
                : "border-zinc-300 text-zinc-700 hover:border-zinc-500"
            } disabled:opacity-50`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {state === "streaming" && (
        <p className="text-xs text-zinc-400">Đang luận giải…</p>
      )}
      {error && (
        <p className="rounded bg-rose-50 p-2 text-xs text-rose-700">
          {error === "llm_unconfigured"
            ? "AI endpoint chưa được cấu hình — thử lại sau."
            : `Lỗi: ${error}`}
        </p>
      )}
      {text && (
        <div className="whitespace-pre-wrap text-sm leading-6 text-zinc-800">
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
