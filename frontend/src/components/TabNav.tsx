"use client";

/** 상단 탭 내비게이션 (T026, contracts/ui-sketches.md 화면 구성). */

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "환율 조회" },
  { href: "/chart", label: "추이 차트" },
  { href: "/spreads", label: "스프레드 설정" },
  { href: "/collection", label: "수집 현황" },
] as const;

export function TabNav() {
  const pathname = usePathname();
  return (
    <nav className="border-b border-gray-200" aria-label="주요 메뉴">
      <ul className="mx-auto flex max-w-5xl gap-1 px-4">
        {TABS.map((tab) => {
          const active = pathname === tab.href;
          return (
            <li key={tab.href}>
              <Link
                href={tab.href}
                aria-current={active ? "page" : undefined}
                className={`inline-block border-b-2 px-4 py-3 text-sm ${
                  active
                    ? "border-gray-900 font-semibold text-gray-900"
                    : "border-transparent text-gray-500 hover:text-gray-800"
                }`}
              >
                {tab.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
