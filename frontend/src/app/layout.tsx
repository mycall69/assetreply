/**
 * 애플리케이션 셸 (T015) — contracts/ui-wireframes.md W1.
 *
 * 왼쪽 고정 사이드바 + 상단 바 + 본문. 001의 4탭 구조를 대체한다.
 */

import type { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import "./globals.css";

export const metadata: Metadata = {
  title: "AssetReplay",
  description: "다중 자산군 히스토리 데이터를 축적하고 투자 성과를 재현·비교한다",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko">
      <body className="bg-white text-gray-900 antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
