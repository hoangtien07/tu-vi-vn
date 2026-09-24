"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { authLogin } from "../../lib/api";

const INPUT =
  "w-full rounded border border-zinc-300 px-2 py-1.5 text-sm dark:border-zinc-700 dark:bg-zinc-900";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await authLogin(email, password);
      router.push("/profiles");
      router.refresh();
    } catch (err) {
      const st = (err as { status?: number }).status;
      setError(
        st === 401
          ? "Email hoặc mật khẩu chưa đúng."
          : st === 429
            ? "Thử lại sau vài phút."
            : "Lỗi đăng nhập.",
      );
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center p-4">
      <h1 className="mb-4 text-xl font-semibold tracking-tight">Đăng nhập</h1>
      <form onSubmit={submit} className="space-y-3">
        <input
          className={INPUT}
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        <input
          className={INPUT}
          type="password"
          placeholder="Mật khẩu (tối thiểu 8 ký tự)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength={8}
          required
        />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded bg-amber-700 py-2 text-sm text-white disabled:opacity-50"
        >
          Đăng nhập
        </button>
      </form>
      <p className="mt-3 text-center text-sm text-zinc-500">
        Chưa có tài khoản?{" "}
        <Link href="/register" className="text-amber-700 hover:underline">
          Đăng ký
        </Link>
      </p>
    </main>
  );
}
