import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "AIRS 情报监测台",
  description: "市场与社媒情报卡片监测平台",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" className="h-full antialiased">
      <body className="min-h-full">
        <div className="min-h-screen bg-neutral-100">
          <header className="border-b border-neutral-200 bg-white">
            <div className="mx-auto flex max-w-7xl items-center justify-between px-5 py-3">
              <Link href="/" className="text-sm font-semibold tracking-normal text-neutral-950">
                AIRS 情报监测台
              </Link>
              <nav className="flex items-center gap-1 text-sm text-neutral-600">
                <Link className="rounded-md px-3 py-1.5 hover:bg-neutral-100 hover:text-neutral-950" href="/">
                  监测台
                </Link>
                <Link className="rounded-md px-3 py-1.5 hover:bg-neutral-100 hover:text-neutral-950" href="/cards">
                  情报卡片
                </Link>
                <Link className="rounded-md px-3 py-1.5 hover:bg-neutral-100 hover:text-neutral-950" href="/sources">
                  来源
                </Link>
                <Link className="rounded-md px-3 py-1.5 hover:bg-neutral-100 hover:text-neutral-950" href="/search">
                  搜索
                </Link>
              </nav>
            </div>
          </header>
          <main className="mx-auto max-w-7xl px-5 py-6">{children}</main>
        </div>
      </body>
    </html>
  );
}
