import Link from "next/link";
import { notFound } from "next/navigation";

import { ChartBoard } from "../../../features/chart/components/ChartBoard";
import { toChartView } from "../../../features/chart/adapters/dto-to-view";
import { getSharedChart } from "../../../lib/api";

export default async function SharedChartPage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  const chart = await getSharedChart(token).catch(() => null);
  if (!chart) notFound();

  return (
    <main className="mx-auto w-full max-w-4xl flex-1 p-4">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-xs text-zinc-500">Lá số được chia sẻ</span>
        <Link
          href="/"
          className="text-sm font-medium text-amber-700 hover:underline"
        >
          Lập lá số của bạn →
        </Link>
      </div>
      <ChartBoard view={toChartView(chart.chart)} />
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
