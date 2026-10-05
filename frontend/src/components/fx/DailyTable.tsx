"use client";

/**
 * 일자별 상세 표 (T032) — contracts/ui-wireframes.md W2.
 *
 * FR-021: 고시가 없는 날은 행을 만들지 않는다. 날짜가 연속하지 않는 것이 정상이며,
 * 없는 값을 만들어 채우는 것은 헌법 원칙 V 위반이다.
 * FR-024: 파생 4종이 "현재 스프레드를 과거에 적용한 가정"임을 밝힌다. 표에서 실측인
 * 열은 매매기준율뿐이다.
 * FR-025: 잠정 행을 확정 행과 구분한다.
 */

import { useEffect, useRef } from "react";
import { PeriodRowBadges } from "@/components/fx/PeriodRowBadges";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { buildDailyCsv, downloadCsv } from "@/lib/csv";
import { formatRate } from "@/lib/format";
import { highlightedRow } from "@/stores/fxWorkspaceStore";
import type { DailyResponse } from "@/lib/types";

const COLUMNS = [
  "날짜", "매매기준율", "현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때",
] as const;

export function DailyTable({
  data,
  selectedDate,
  onSelect,
  onLoadMore,
  loadingMore = false,
  loadError = null,
  resetKey = 0,
}: {
  data: DailyResponse;
  selectedDate: string | null;
  onSelect: (date: string) => void;
  onLoadMore: () => void;
  loadingMore?: boolean;
  loadError?: string | null;
  resetKey?: number;
}) {
  const root = useRef<HTMLDivElement>(null);

  // 실패한 동안에는 감시를 끊는다. 즉시 다시 관찰하면 같은 오류를 무한히 반복한다 —
  // 재시도는 사람이 고른다 (FR-004).
  const open = data.hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);

  // FR-005b: 표가 통째로 바뀌면 스크롤을 처음으로 되돌린다. 이전 위치에 머무르면
  // 새로 받은 내용과 화면이 어긋난다. **`resetKey`가 정말 바뀌었을 때만** 움직인다(010 R10-16) —
  // "첫 렌더인가"로 가르면 StrictMode가 효과를 두 번 실행해 다시 붙은 표가 창을 표로 옮겼다
  // (통화를 바꾸면 표가 떨어졌다 다시 붙는다).
  const shown = useRef(resetKey);
  useEffect(() => {
    if (shown.current === resetKey) return;
    shown.current = resetKey;
    root.current?.scrollIntoView?.({ block: "start" });
  }, [resetKey]);

  // 선택 날짜가 **속한 구간**의 행을 강조한다 (FR-019). 기준일과 대조하면 주·월
  // 단위에서 강조가 거의 사라진다.
  const highlight = highlightedRow(data, selectedDate);
  const periodName = data.period === "weekly" ? "주" : "달";
  const note =
    data.period === "daily" || selectedDate === null
      ? null
      : highlight === null
        ? `선택한 ${selectedDate}이 속한 ${periodName}에는 고시가 없습니다`
        : highlight.date === selectedDate
          ? null
          : `선택한 ${selectedDate}이 속한 ${periodName}의 값입니다`;

  const download = () => {
    // 화면에 쌓인 행을 대상으로 한다. 값은 서버가 준 문자열을 그대로 쓴다 (FR-045).
    // 담긴 범위는 파일 머리말이 밝힌다 (FR-016c).
    const first = data.rows.at(0)?.date ?? "range";
    downloadCsv(
      `fx-${data.currency}-${data.period}-${first}.csv`, buildDailyCsv(data));
  };

  return (
    <div ref={root} className="rounded-lg border border-gray-200">
      <div className="flex items-center justify-end border-b border-gray-100 px-4 py-2">
        <button
          type="button"
          onClick={download}
          className="rounded border border-gray-300 px-2.5 py-1 text-xs text-gray-700 hover:bg-gray-50"
        >
          ⤓ 내려받기
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              {COLUMNS.map((c, i) => (
                <th
                  key={c}
                  scope="col"
                  className={`px-4 py-2.5 font-normal ${i === 0 ? "text-left" : "text-right"}`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row) => {
              const active = highlight !== null && row.date === highlight.date;
              return (
                <tr
                  key={row.date}
                  aria-selected={active}
                  onClick={() => onSelect(row.date)}
                  className={`cursor-pointer border-b border-gray-100 last:border-0 ${
                    active ? "bg-amber-50 font-semibold" : "hover:bg-gray-50"
                  }`}
                >
                  <td className="px-4 py-2 tabular-nums">
                    {row.date}
                    {row.isProvisional && (
                      <span title="잠정값" className="ml-1 text-amber-600">
                        ⚠
                      </span>
                    )}
                    <PeriodRowBadges row={row} unit={data.period} />
                  </td>
                  <td className="px-4 py-2 text-right font-medium tabular-nums">
                    {formatRate(row.baseRate)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatRate(row.derived.cashBuy)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatRate(row.derived.cashSell)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatRate(row.derived.remitSend)}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {formatRate(row.derived.remitReceive)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {note !== null && (
        // FR-019a: 강조된 행의 날짜가 선택 날짜와 다르다는 사실을 알린다. 알리지
        // 않으면 사용자는 자신이 고른 날짜가 바뀌었다고 오해한다.
        // FR-020: 속한 구간에 행이 없으면 강조가 그냥 사라진다 — 선택이 풀린 것으로
        // 오해하므로 사라진 이유를 밝힌다.
        <p
          data-testid="highlight-note"
          aria-live="polite"
          className="border-t border-gray-100 bg-amber-50/50 px-4 py-2 text-xs text-gray-600"
        >
          {note}
        </p>
      )}

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        <span className="mr-2 text-amber-600">⚠ 잠정값</span>
        {data.period !== "daily" && (
          <>
            <span className="mr-2">📅 기준일이 옮겨진 행</span>
            <span className="mr-2">⏳ 아직 끝나지 않은 구간</span>
          </>
        )}
        파생 환율 4종은 현재 스프레드를 각 날짜에 적용한 가정입니다. 실측값은 매매기준율뿐입니다.
      </p>

      {/*
        이어 보기 상태 — contracts/ui-wireframes.md W3.

        `더 보기` 버튼이 사라진 만큼 **상태를 말로 알려야** 한다. 끝에 도달했는데
        알리지 않으면 사용자는 아직 받는 중이라고 여겨 기다린다(FR-002). 조용히
        멈추면 데이터가 거기서 끝난 것으로 오해한다(FR-004).

        알림 역할(`role="status"`)을 두는 이유는 눈으로 보는 사용자만 끝을 알면
        FR-002가 절반만 성립하기 때문이다 (ui-wireframes 접근성).
      */}
      <div className="flex items-center justify-center gap-3 border-t border-gray-100 px-4 py-3 text-xs">
        <span role="status" aria-live="polite" className="text-gray-500">
          {loadError
            ? loadError
            : loadingMore
              ? "⟳ 불러오는 중…"
              : !data.hasMore
                ? `${data.oldestReturned ?? "처음"}까지 모두 표시했습니다`
                : ""}
        </span>
        {loadError !== null && (
          <button
            type="button"
            onClick={onLoadMore}
            className="rounded border border-gray-300 px-2.5 py-1 text-gray-700 hover:bg-gray-50"
          >
            다시 시도
          </button>
        )}
      </div>

      {data.hasMore && loadError === null && (
        // 화면에 들어오면 이어 보기가 시작된다. 표가 화면보다 짧아 스크롤이 일어나지
        // 않아도 보이기만 하면 시작된다 (FR-001a).
        <div ref={sentinel} data-testid="scroll-sentinel" aria-hidden="true" className="h-px" />
      )}
    </div>
  );
}
