import type { Metadata } from "next";
import Link from "next/link";
import { Geist, Geist_Mono } from "next/font/google";

import { AuthNav } from "../features/auth/components/AuthNav";

import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Tử Vi Việt Nam",
  description: "Hệ thống luận giải Tử Vi có kiểm chứng",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="vi"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <header className="flex items-center justify-between border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
          <Link href="/" className="text-sm font-semibold tracking-tight">
            Tử Vi Việt Nam
          </Link>
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/profiles" className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400">
              Hồ sơ
            </Link>
            <Link href="/compatibility" className="text-zinc-600 hover:text-zinc-900 dark:text-zinc-400">
              Hợp bàn
            </Link>
            <AuthNav />
          </nav>
        </header>
        {children}
      </body>
    </html>
  );
}
