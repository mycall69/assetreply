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

import { buildDailyCsv, downloadCsv } from "@/lib/csv";
import { formatRate } from "@/lib/format";
import type { DailyResponse } from "@/lib/types";

const COLUMNS = [
  "날짜", "매매기준율", "현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때",
] as const;

export function DailyTable({
  data,
  selectedDate,
  onSelect,
  onLoadMore,
}: {
  data: DailyResponse;
  selectedDate: string | null;
  onSelect: (date: string) => void;
  onLoadMore: () => void;
}) {
  const download = () => {
    // 화면에 표시된 행을 대상으로 한다. 값은 서버가 준 문자열을 그대로 쓴다 (FR-045).
    const first = data.rows.at(0)?.date ?? "range";
    downloadCsv(`fx-${data.currency}-${first}.csv`, buildDailyCsv(data));
  };

  return (
    <div className="rounded-lg border border-gray-200">
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
              const active = row.date === selectedDate;
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

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        <span className="mr-2 text-amber-600">⚠ 잠정값</span>
        파생 환율 4종은 현재 스프레드를 각 날짜에 적용한 가정입니다. 실측값은 매매기준율뿐입니다.
      </p>

      {data.hasMore && (
        <div className="border-t border-gray-100 px-4 py-3 text-center">
          <button
            type="button"
            onClick={onLoadMore}
            className="rounded border border-gray-300 px-4 py-1.5 text-sm text-gray-700 hover:bg-gray-50"
          >
            더 보기
          </button>
        </div>
      )}
    </div>
  );
}
