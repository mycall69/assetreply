"use client";

/**
 * 상단 바 (T013) — contracts/ui-wireframes.md W1.
 *
 * FR-004: 현재 화면의 이름을 표시한다. 우측에는 수집 진행 표시기가 붙는다(FR-049).
 */

import { usePathname } from "next/navigation";
import { CollectionIndicator } from "./CollectionIndicator";

const TITLES: ReadonlyArray<readonly [string, string]> = [
  ["/fx/collection", "수집 현황"],
  ["/fx", "외환"],
  ["/settings", "설정"],
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
