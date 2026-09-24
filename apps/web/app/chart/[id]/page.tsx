import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartBoard } from "../../../features/chart/components/ChartBoard";
import { toChartView } from "../../../features/chart/adapters/dto-to-view";
import { getChart } from "../../../lib/api";

export default async function ChartPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const chart = await getChart(id).catch(() => null);
  if (!chart) notFound();

  const view = toChartView(chart.chart);

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 p-4">
      <div className="mb-4 flex items-center justify-between">
        <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
          ← Lập lá số khác
        </Link>
        <span className="font-mono text-[10px] text-zinc-400">
          {chart.chartHash.slice(0, 16)}…
        </span>
      </div>
      <ChartBoard view={view} />
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
