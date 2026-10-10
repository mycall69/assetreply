/**
 * 애플리케이션 셸 (T015) — contracts/ui-wireframes.md W1.
 *
 * 왼쪽 고정 사이드바 + 상단 바 + 본문. 001의 4탭 구조를 대체한다.
 *
 * 014 반복 2026-10-10c(FR-030): `<head>`의 깜빡임 방지 스크립트가 그리기 전에 고른 테마(`dark` 클래스)를 단다. 서버는 그 클래스를 모르므로
 * `<html>`의 속성 차이를 React가 경고하지 않게 한다(`suppressHydrationWarning` — 이 요소 하나의 속성만).
 */

import type { Metadata } from "next";
import { AppShell } from "@/components/shell/AppShell";
import { THEME_SCRIPT } from "@/lib/themeScript";
import "./globals.css";

export const metadata: Metadata = {
  title: "AssetReplay",
  description: "다중 자산군 히스토리 데이터를 축적하고 투자 성과를 재현·비교한다",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="bg-white text-gray-900 antialiased">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
