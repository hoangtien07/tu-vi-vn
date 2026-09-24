import Link from "next/link";

import { CompatibilityClient } from "../../features/compatibility/components/CompatibilityClient";

export default async function CompatibilityPage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;

  return (
    <main className="mx-auto w-full max-w-3xl flex-1 p-4">
      <div className="mb-4 flex items-center justify-between">
        <Link href="/" className="text-sm text-zinc-500 hover:text-zinc-900">
          ← Lập lá số
        </Link>
        <Link
          href="/compatibility"
          className="text-xs text-zinc-400 hover:text-zinc-700"
        >
          Hợp bàn
        </Link>
      </div>
      <h1 className="mb-1 text-xl font-semibold tracking-tight">
        Hợp bàn hai lá số
      </h1>
      <p className="mb-4 text-sm text-zinc-600">
        Đối chiếu tứ hóa và cung Mệnh–Phu của hai lá số — mọi luận giải kèm căn
        cứ kiểm chứng, không chấm điểm.
      </p>
      <CompatibilityClient initialA={a ?? ""} initialB={b ?? ""} />
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
