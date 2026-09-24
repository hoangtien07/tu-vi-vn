import Link from "next/link";
import { notFound } from "next/navigation";

import { getReading } from "../../../../../lib/api";
import { ReadingReopenBeacon } from "../../../../../features/chart/components/ReadingReopenBeacon";

export default async function ReadingPage({
  params,
}: {
  params: Promise<{ id: string; runId: string }>;
}) {
  const { id, runId } = await params;
  const r = await getReading(id, runId).catch(() => null);
  if (!r) notFound();

  return (
    <main className="mx-auto w-full max-w-2xl flex-1 p-4">
      <ReadingReopenBeacon chartId={id} />
      <div className="mb-4">
        <Link
          href={`/chart/${id}/readings`}
          className="text-sm text-zinc-500 hover:text-zinc-900"
        >
          ← Bài luận đã lưu
        </Link>
      </div>
      <h1 className="mb-1 text-xl font-semibold tracking-tight">
        Bài luận {r.isCompatibility ? "hợp bàn" : ""} · {r.topic}
      </h1>
      <p className="mb-4 text-xs text-zinc-400">
        {r.targetDate && <>mục tiêu {r.targetDate} · </>}
        {new Date(r.createdAt).toLocaleString("vi-VN")}
      </p>
      {r.outputText ? (
        <div className="whitespace-pre-wrap rounded-lg border border-zinc-200 p-4 text-sm leading-6 dark:border-zinc-700">
          {r.outputText}
        </div>
      ) : (
        <p className="text-sm text-zinc-500">
          Bài luận chưa hoàn tất ({r.status}).
        </p>
      )}
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
