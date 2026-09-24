import Link from "next/link";
import { notFound } from "next/navigation";

import { getChart, getReadings } from "../../../../lib/api";

const TOPIC_LABELS: Record<string, string> = {
  overview: "Tổng quan",
  career: "Công việc",
  wealth: "Tài chính",
  love: "Tình cảm",
  health: "Sức khỏe",
};

const STATUS_LABELS: Record<string, string> = {
  completed: "Hoàn tất",
  failed: "Lỗi",
  pending: "Đang chạy",
  aborted: "Đã hủy",
};

export default async function ReadingsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const chart = await getChart(id).catch(() => null);
  if (!chart) notFound();
  const readings = await getReadings(id).catch(() => []);

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 p-4">
      <div className="mb-4">
        <Link
          href={`/chart/${id}`}
          className="text-sm text-zinc-500 hover:text-zinc-900"
        >
          ← Lá số
        </Link>
      </div>
      <h1 className="mb-4 text-xl font-semibold tracking-tight">
        Bài luận đã lưu
      </h1>
      {readings.length === 0 && (
        <p className="text-sm text-zinc-500">Chưa có bài luận nào.</p>
      )}
      <ul className="space-y-2">
        {readings.map((r) => (
          <li
            key={r.id}
            className="flex items-center justify-between rounded-lg border border-zinc-200 px-3 py-2 text-sm dark:border-zinc-700"
          >
            <div>
              <span className="font-medium">
                {TOPIC_LABELS[r.topic] ?? r.topic}
              </span>
              {r.isCompatibility && (
                <span className="ml-2 text-xs text-amber-700">· hợp bàn</span>
              )}
              {r.targetDate && (
                <span className="ml-2 text-xs text-zinc-400">
                  → {r.targetDate}
                </span>
              )}
            </div>
            <div className="text-xs text-zinc-400">
              {STATUS_LABELS[r.status] ?? r.status} ·{" "}
              {new Date(r.createdAt).toLocaleDateString("vi-VN")}
            </div>
          </li>
        ))}
      </ul>
    </main>
  );
}
