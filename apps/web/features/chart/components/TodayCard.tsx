"use client";

import { useCallback, useEffect, useState } from "react";

import {
  getToday,
  trackEvent,
  type ChatTarget,
  type TodayFacts,
} from "../../../lib/api";
import { ChatPanel } from "./ChatPanel";

const TOPIC_LABELS: Record<string, string> = {
  overview: "Tổng quan",
  career: "Công việc",
  wealth: "Tài chính",
  love: "Quan hệ",
  health: "Sức khỏe",
};

export function TodayCard({ chartId }: { chartId: string }) {
  const [data, setData] = useState<TodayFacts | null>(null);
  const [error, setError] = useState("");
  const [showFacts, setShowFacts] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [state, setState] = useState<"idle" | "streaming" | "done" | "error">(
    "idle",
  );
  const [text, setText] = useState("");

  useEffect(() => {
    getToday(chartId)
      .then((d) => {
        setData(d);
        trackEvent("today_opened", { chartId });
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Lỗi tải"));
  }, [chartId]);

  const brief = useCallback(async () => {
    if (state === "streaming") return;
    setState("streaming");
    setText("");
    trackEvent("today_brief", { chartId });
    try {
      const resp = await fetch(`/api/charts/${chartId}/today/brief`, {
        method: "POST",
      });
      if (!resp.ok || !resp.body) {
        setState("error");
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
          const raw = i >= 0 ? frame.slice(i + 6) : undefined;
          if (!ev || !raw) continue;
          const payload = JSON.parse(raw);
          if (ev === "delta") setText((x) => x + payload);
          else if (ev === "replace") setText(payload);
          else if (ev === "done") setState("done");
          else if (ev === "error") setState("error");
        }
      }
      setState((s) => (s === "streaming" ? "done" : s));
    } catch {
      setState("error");
    }
  }, [chartId, state]);

  const todayTarget: ChatTarget | undefined = data
    ? {
        scope: "daily",
        year: Number(data.date.slice(0, 4)),
        month: Number(data.date.slice(5, 7)),
        day: Number(data.date.slice(8, 10)),
      }
    : undefined;

  return (
    <section className="mt-4 rounded-lg border border-zinc-200 p-4 dark:border-zinc-700">
      <h2 className="mb-1 text-sm font-semibold tracking-tight">
        Hôm nay{data ? ` — ${data.date}` : ""}
      </h2>
      {error && <p className="text-xs text-red-600">{error}</p>}
      {data && (
        <ul className="space-y-1 text-sm leading-6">
          {data.highlights.map((h, i) => (
            <li key={i}>
              <span className="font-medium">
                {TOPIC_LABELS[h.topicHint] ?? h.topicHint}
              </span>{" "}
              — {h.summary}
            </li>
          ))}
          {data.highlights.length === 0 && (
            <li className="text-zinc-500">Ngày bình thường, không điểm nổi.</li>
          )}
        </ul>
      )}
      <div className="mt-2 flex flex-wrap gap-3 text-sm">
        <button
          onClick={() => setShowFacts((v) => !v)}
          className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400"
        >
          {showFacts ? "Ẩn căn cứ" : "Căn cứ"}
        </button>
        <button
          onClick={brief}
          disabled={state === "streaming"}
          className="text-amber-700 hover:underline disabled:opacity-50"
        >
          Luận chi tiết hôm nay
        </button>
        <button
          onClick={() => setShowChat((v) => !v)}
          className="text-amber-700 hover:underline"
        >
          Hỏi thêm
        </button>
      </div>
      {showFacts && data && (
        <pre className="mt-2 max-h-56 overflow-y-auto rounded bg-zinc-50 p-2 text-xs dark:bg-zinc-900">
          {JSON.stringify(data.facts, null, 2)}
        </pre>
      )}
      {(state === "streaming" || state === "done") && (
        <div className="mt-2 whitespace-pre-wrap text-sm leading-6">{text}</div>
      )}
      {state === "error" && (
        <p className="mt-2 text-xs text-red-600">
          AI endpoint chưa được cấu hình — thử lại sau.
        </p>
      )}
      {showChat && data && (
        <ChatPanel
          chartId={chartId}
          target={todayTarget}
          onClose={() => setShowChat(false)}
        />
      )}
    </section>
  );
}
