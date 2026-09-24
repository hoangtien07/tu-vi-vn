"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { createProfile } from "../../../lib/api";

const INPUT =
  "w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export function SaveToProfile({ chartId }: { chartId: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [relationship, setRelationship] = useState("self");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const save = async () => {
    if (!name.trim()) {
      setError("Nhập tên hiển thị.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createProfile({
        display_name: name.trim(),
        relationship,
        chart_id: chartId,
      });
      router.push("/profiles");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Lỗi lưu hồ sơ");
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="text-sm text-amber-700 hover:underline"
      >
        Lưu vào hồ sơ của tôi
      </button>
    );
  }

  return (
    <div className="mx-auto mt-3 flex max-w-sm flex-col gap-2 rounded-lg border border-zinc-200 p-3 dark:border-zinc-700">
      <input
        className={INPUT}
        placeholder="Tên hiển thị (vd: Mẹ, Tiến…)"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />
      <select
        className={INPUT}
        value={relationship}
        onChange={(e) => setRelationship(e.target.value)}
      >
        <option value="self">Bản thân</option>
        <option value="partner">Bạn đời</option>
        <option value="mother">Mẹ</option>
        <option value="father">Bố</option>
        <option value="child">Con</option>
        <option value="friend">Bạn</option>
        <option value="other">Khác</option>
      </select>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <button
        onClick={save}
        disabled={busy}
        className="rounded bg-amber-600 px-3 py-1.5 text-sm text-white hover:bg-amber-700 disabled:opacity-50"
      >
        {busy ? "Đang lưu…" : "Lưu hồ sơ"}
      </button>
    </div>
  );
}
