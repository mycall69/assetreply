"use client";

/**
 * 상단 바 (T013) — contracts/ui-wireframes.md W1.
 *
 * FR-004: 현재 화면의 이름을 표시한다. 우측에는 수집 진행 표시기가 붙는다(FR-049).
 */

import { usePathname } from "next/navigation";
import { CollectionIndicator } from "./CollectionIndicator";

/**
 * 경로 → 제목. 사이드바에 경로를 더하면 여기에도 더한다 — 빠뜨리면 마지막 줄(`/`)에 걸려 "대시보드"로 보인다(005·007·008이
 * 그랬다). `TopBarTitle.test.ts`가 사이드바의 메뉴마다 확인한다.
 */
const TITLES: ReadonlyArray<readonly [string, string]> = [
  ["/fx/collection", "수집 현황"],
  ["/fx", "외환"],
  ["/crypto", "가상자산"],
  ["/stocks", "주식"],
  ["/deposit", "예금"],
  ["/realestate", "부동산"],
  ["/compare", "투자 비교"],
  ["/settings", "설정"],
  // 014 — 대시보드와 지표 화면(`/dashboard/{지표}`).
  ["/dashboard", "대시보드"],
  ["/", "대시보드"],
];

export function screenTitle(pathname: string): string {
  // 더 구체적인 경로가 앞에 오도록 정렬해 두었다. 첫 일치를 쓴다.
  return TITLES.find(([prefix]) => pathname.startsWith(prefix))?.[1] ?? "AssetReplay";
}

export function TopBar() {
  const pathname = usePathname();
  return (
    <header className="flex h-14 items-center justify-between border-b border-gray-200 px-6">
      <h1 className="text-base font-semibold text-gray-900">{screenTitle(pathname)}</h1>
      <CollectionIndicator />
    </header>
  );
}
