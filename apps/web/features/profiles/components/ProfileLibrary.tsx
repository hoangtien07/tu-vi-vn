"use client";

import Link from "next/link";
import { useState } from "react";

import { deleteProfile, type ApiProfile } from "../../../lib/api";

const RELATIONSHIP_LABELS: Record<string, string> = {
  self: "Bản thân",
  partner: "Bạn đời",
  mother: "Mẹ",
  father: "Bố",
  child: "Con",
  friend: "Bạn",
  other: "Khác",
};

export function ProfileLibrary({ initial }: { initial: ApiProfile[] }) {
  const [profiles, setProfiles] = useState(initial);
  const [deleting, setDeleting] = useState<string | null>(null);

  const remove = async (id: string) => {
    if (!confirm("Xóa hồ sơ này? Lá số gốc vẫn giữ.")) return;
    setDeleting(id);
    try {
      await deleteProfile(id);
      setProfiles((ps) => ps.filter((p) => p.id !== id));
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {profiles.map((p) => (
        <div
          key={p.id}
          className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-700"
        >
          <div className="mb-1 flex items-center justify-between">
            <span className="font-medium">{p.displayName}</span>
            {p.relationship && (
              <span className="text-xs text-zinc-400">
                {RELATIONSHIP_LABELS[p.relationship] ?? p.relationship}
              </span>
            )}
          </div>
          <div className="mt-2 flex items-center gap-3 text-sm">
            <Link
              href={`/chart/${p.chartId}`}
              className="text-amber-700 hover:underline"
            >
              Xem lá số
            </Link>
            <Link
              href={`/chart/${p.chartId}/time`}
              className="text-amber-700 hover:underline"
            >
              Vận trình
            </Link>
            <button
              onClick={() => remove(p.id)}
              disabled={deleting === p.id}
              className="ml-auto text-xs text-zinc-400 hover:text-red-600"
            >
              Xóa
            </button>
          </div>
        </div>
      ))}
      <Link
        href="/"
        className="flex items-center justify-center rounded-lg border border-dashed border-zinc-300 p-4 text-sm text-zinc-500 hover:border-amber-500 hover:text-amber-700 dark:border-zinc-700"
      >
        + Thêm người
      </Link>
    </div>
  );
}
