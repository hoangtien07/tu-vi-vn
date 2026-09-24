import Link from "next/link";

import { ProfileLibrary } from "../../features/profiles/components/ProfileLibrary";
import { listProfiles } from "../../lib/api";

export default async function ProfilesPage() {
  const profiles = await listProfiles().catch(() => []);

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
      <h1 className="mb-4 text-xl font-semibold tracking-tight">Hồ sơ của tôi</h1>
      <ProfileLibrary initial={profiles} />
      <p className="mt-4 text-center text-xs text-zinc-400">
        Mang tính tham khảo — luận giải theo mệnh lý học truyền thống.
      </p>
    </main>
  );
}
