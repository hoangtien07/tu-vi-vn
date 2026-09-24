import Link from "next/link";
import { notFound } from "next/navigation";

import { TimeNavigator } from "../../../../features/chart/components/TimeNavigator";
import { getChart } from "../../../../lib/api";

export default async function TimePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const chart = await getChart(id).catch(() => null);
  if (!chart) notFound();

  const meta = chart.chart.chart.meta as { solarDate?: string };
  const birthYear = Number(meta?.solarDate?.slice(0, 4) ?? 1900);

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-4">
      <div className="mb-4 flex items-center justify-between">
        <Link
          href={`/chart/${id}`}
          className="text-sm text-zinc-500 hover:text-zinc-900"
        >
          ← Lá số
        </Link>
        <Link
          href="/profiles"
          className="text-xs text-zinc-400 hover:text-zinc-700"
        >
          Hồ sơ
        </Link>
      </div>
      <h1 className="mb-4 text-xl font-semibold tracking-tight">Vận trình</h1>
      <TimeNavigator chartId={id} birthYear={birthYear} />
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
