/**
 * 이름을 외부 시세 페이지 링크로 (010 반복 1, T049) — FR-024~FR-026, ui-wireframes F5.
 *
 * 새 탭으로 연다(`noopener noreferrer` — 연 페이지가 이 화면을 조작하지 못한다). 누름이 행으로 올라가지 않게 막는다 — 이력 행의 고르기·다시
 * 실행이 함께 일어나면 사용자가 링크만 눌렀는데 결과가 바뀐다. 규칙을 모르는 자산(`href`가 `null`)은 이름만 둔다.
 */

import type { ReactNode } from "react";

export function ExternalLink({
  href,
  label,
  className,
  children,
}: {
  href: string | null;
  /** 접근 이름 — 이름과 어디로 가는지. */
  label: string;
  className?: string;
  children: ReactNode;
}) {
  if (href === null) return <span className={className}>{children}</span>;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" aria-label={label}
      onClick={(e) => e.stopPropagation()}
      className={`underline decoration-gray-300 underline-offset-2 hover:text-blue-700 hover:decoration-blue-700 ${className ?? ""}`}>
      {children}
    </a>
  );
}
