"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { authLogout, authMe, type AuthUser } from "../../../lib/api";

export function AuthNav() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loaded, setLoaded] = useState(false);
  const router = useRouter();

  useEffect(() => {
    authMe()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoaded(true));
  }, []);

  const logout = async () => {
    await authLogout().catch(() => {});
    setUser(null);
    router.refresh();
  };

  if (!loaded) return null;
  return user ? (
    <span className="flex items-center gap-3 text-sm">
      <span className="text-zinc-600 dark:text-zinc-400">{user.email}</span>
      <button onClick={logout} className="text-amber-700 hover:underline">
        Đăng xuất
      </button>
    </span>
  ) : (
    <Link href="/login" className="text-sm text-amber-700 hover:underline">
      Đăng nhập
    </Link>
  );
}
