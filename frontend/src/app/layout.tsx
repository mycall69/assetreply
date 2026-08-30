/**
 * 애플리케이션 셸 — 헤더와 4탭 내비게이션 (T026).
 *
 * contracts/ui-sketches.md의 화면 구성을 따른다.
 */

import type { Metadata } from "next";
import { TabNav } from "@/components/TabNav";
import "./globals.css";

export const metadata: Metadata = {
  title: "AssetReplay · 외환",
  description: "통화별 최장 구간의 환율을 축적하고 조회·시각화한다",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-white text-gray-900 antialiased">
        <header className="border-b border-gray-200">
          <div className="mx-auto max-w-5xl px-4 py-4">
            <h1 className="text-lg font-semibold">AssetReplay · 외환</h1>
          </div>
        </header>
        <TabNav />
        <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
