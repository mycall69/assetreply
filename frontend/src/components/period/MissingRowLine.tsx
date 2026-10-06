"use client";

/**
 * 결측 구간 행 (012 T033) — FR-004b, contracts/ui-wireframes.md F4. 가상자산 일 단위 표 둘이 함께 쓴다.
 *
 * 연속된 출처 결측 구간 하나를 **한 칸에 걸친 글**로 보인다 — "2021-03-08~03-12 출처 결측 — 값 없음". 값 칸을 두지 않는다 — 메우지 않는다(원칙 V).
 * 조용히 빠지면 사용자는 그날 데이터가 없다는 것을 표에서 알 수 없고, 앞뒤 행의 변화를 하루치 변화로 읽는다.
 */

import type { MissingRow } from "@/lib/types";

/** "2021-03-08~03-12" — 같은 해면 끝의 해를 줄인다. 하루면 그날 하나다. */
export function missingSpan(row: MissingRow): string {
  if (row.date === row.dateTo) return row.date;
  const sameYear = row.date.slice(0, 4) === row.dateTo.slice(0, 4);
  return `${row.date}~${sameYear ? row.dateTo.slice(5) : row.dateTo}`;
}

export function MissingRowLine({ row, colSpan }: { row: MissingRow; colSpan: number }) {
  return (
    <tr data-kind="missing" className="border-b border-gray-100 bg-gray-50 last:border-0">
      {/* 한 덩어리의 글이다 — 날짜와 사유를 나눠 그리면 화면 읽기 프로그램이 따로 읽는다 */}
      <td colSpan={colSpan} className="whitespace-nowrap px-1.5 py-1.5 text-left tabular-nums text-gray-500">
        {`${missingSpan(row)} 출처 결측 — 값 없음`}
      </td>
    </tr>
  );
}
