"use client";

import { useState } from "react";

import {
  sendChat,
  type ChatTarget,
} from "../../../lib/api";

interface Msg {
  role: "user" | "assistant";
  text: string;
}

export function ChatPanel({
  chartId,
  target,
  onClose,
}: {
  chartId: string;
  target?: ChatTarget;
  onClose: () => void;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setError("");
    setMsgs((m) => [...m, { role: "user", text }]);
    try {
      const r = await sendChat(chartId, text, conversationId, target);
      setConversationId(r.conversationId);
      setMsgs((m) => [...m, { role: "assistant", text: r.reply }]);
    } catch (e) {
      setError(
        e instanceof Error && e.message.includes("503")
          ? "AI endpoint chưa được cấu hình — thử lại sau."
          : "Lỗi gửi câu hỏi.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-medium">
          Hỏi thêm {target ? `(vận ${target.scope})` : ""}
        </span>
        <button
          onClick={onClose}
          className="text-xs text-zinc-400 hover:text-zinc-700"
        >
          Đóng
        </button>
      </div>
      <div className="mb-2 max-h-56 space-y-2 overflow-y-auto">
        {msgs.map((m, i) => (
          <p
            key={i}
            className={`text-sm leading-6 ${
              m.role === "user" ? "text-right text-zinc-500" : ""
            }`}
          >
            {m.text}
          </p>
        ))}
        {busy && <p className="text-xs text-zinc-400">Đang trả lời…</p>}
        {error && <p className="text-xs text-red-600">{error}</p>}
      </div>
      <div className="flex gap-2">
        <input
          className="flex-1 rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          placeholder="Hỏi về lá số…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          maxLength={2000}
        />
        <button
          onClick={send}
          disabled={busy}
          className="rounded bg-amber-700 px-3 text-sm text-white disabled:opacity-50"
        >
          Gửi
        </button>
      </div>
    </div>
  );
}
