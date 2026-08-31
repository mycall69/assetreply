"use client";

/**
 * 전역 내비게이션 사이드바 (T012) — contracts/ui-wireframes.md W1.
 *
 * FR-005: 아직 구현되지 않은 자산군은 준비 중임이 드러나야 하며, 선택 시 빈 화면이나
 * 오류로 이어져서는 안 된다. 가장 확실한 방법은 **이동할 경로를 만들지 않는 것**이다
 * (research R2-9). 준비되지 않은 항목은 링크가 아니고 키보드 포커스 대상도 아니다 —
 * 포커스가 갔는데 아무 일도 일어나지 않는 상태가 가장 혼란스럽다.
 *
 * 헌법 원칙 IX와의 관계: 이 목록은 정적 레이블일 뿐이며 다른 자산군의 수집·API·데이터
 * 모델을 한 줄도 만들지 않는다. 원칙이 금지하는 것은 여러 자산군의 구현을 벌여놓는 것이다.
 */

import Link from "next/link";

export interface MenuItem {
  readonly label: string;
  /** 준비된 항목만 경로를 가진다. 없으면 이동할 수 없다. */
  readonly href?: string;
}

/** 헌법 원칙 IX가 고정한 자산군 순서를 따른다. */
export const MENU: readonly MenuItem[] = [
  { label: "대시보드" },
  { label: "외환", href: "/fx" },
  { label: "주식" },
  { label: "가상자산" },
  { label: "예금" },
  { label: "부동산" },
  { label: "투자 비교" },
  { label: "설정", href: "/settings" },
];

export function Sidebar({ current }: { current: string }) {
  return (
    <nav
      className="flex h-full w-56 shrink-0 flex-col border-r border-gray-200 bg-gray-50"
      aria-label="자산군 메뉴"
    >
      <div className="px-5 py-5">
        <p className="text-lg font-bold tracking-tight text-gray-900">AssetReplay</p>
        <p className="text-xs text-gray-500">Professional Simulation</p>
      </div>

      <ul className="mt-2 flex flex-col">
        {MENU.map((item) => {
          const ready = item.href !== undefined;
          const active = ready && current.startsWith(item.href as string);
          return (
            <li
              key={item.label}
              aria-current={active ? "page" : undefined}
              className={
                active
                  ? "border-l-4 border-gray-900 bg-white"
                  : "border-l-4 border-transparent"
              }
            >
              {ready ? (
                <Link
                  href={item.href as string}
                  className={`block px-4 py-2.5 text-sm ${
                    active ? "font-semibold text-gray-900" : "text-gray-600 hover:text-gray-900"
                  }`}
                >
                  {item.label}
                </Link>
              ) : (
                // 링크도 버튼도 아니다. 탭 순서에서 자연히 빠진다.
                <span className="flex items-center justify-between px-4 py-2.5 text-sm text-gray-400">
                  {item.label}
                  <span className="rounded bg-gray-200 px-1.5 py-0.5 text-[10px] text-gray-500">
                    준비중
                  </span>
                </span>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
