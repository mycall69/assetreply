"use client";

/**
 * 지표 모달의 일자별 표 (014 반복 2026-10-10b T121) — FR-013, FR-014, FR-029, SC-012, contracts D7.
 *
 * - 칸 일곱: 날짜·시가·고가·저가·종가·대비·등락률. **서버 문자열에 형식만 입힌다**(원칙 VI) — 대비·등락률도 서버가 낸 값이다. 값이 없으면 "—"
 * - 날짜: 일은 `MM-DD`(맨 위 행과 해가 다르면 `YYYY-MM-DD`). 📅 옮김(`shiftedFrom`), ⏳ 끝나지 않은 구간(`isOngoing`), ⏳ 잠정(`provisional`)은
 *   글자로도 적는다 — 기호만으로 전달하지 않는다
 * - 결측 구간 행(일 단위만)은 값이 없다 — 날짜 둘만(원칙 V)
 * - 환율은 외환 고시라 하루 한 값이다(시가·고가·저가 "—")
 * - 아래로 스크롤하면 더 받는다(`useInfiniteScroll` — 주식 일자별 표와 같다). `더 보기` 단추를 두지 않는다
 * - 손익을 색만으로 구별하지 않는다 — ▲/▼를 함께 쓴다
 */
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import { formatPercent, formatRate } from "@/lib/format";
import type { IndicatorTablePeriod, IndicatorTableResponse, IndicatorTableRow } from "@/lib/types";

const COLUMNS = ["날짜", "시가", "고가", "저가", "종가", "대비", "등락률"] as const;

const PERIODS: { period: IndicatorTablePeriod; label: string }[] = [
  { period: "daily", label: "일" },
  { period: "weekly", label: "주" },
  { period: "monthly", label: "월" },
];

const CELL = "px-2 py-1.5 text-right tabular-nums";

type PeriodRow = Extract<IndicatorTableRow, { kind: "period" }>;

function value(raw: string | null): string {
  return raw === null ? "—" : formatRate(raw);
}

function changeText(raw: string | null): string {
  if (raw === null) return "—";
  if (raw.startsWith("-")) return `▼ ${formatRate(raw.slice(1))}`;
  return /[1-9]/.test(raw) ? `▲ ${formatRate(raw)}` : formatRate(raw);
}

function tone(raw: string | null): string {
  if (raw === null || !/[1-9]/.test(raw)) return "text-gray-700";
  return raw.startsWith("-") ? "text-blue-700" : "text-red-700";
}

function Marks({ row }: { row: PeriodRow }) {
  return (
    <>
      {row.shiftedFrom !== undefined && (
        <span className="ml-1 text-xs text-gray-500" title={`기준일 ${row.shiftedFrom}에 값이 없어 ${row.date} 값입니다`}>
          📅 옮김
        </span>
      )}
      {row.isOngoing === true && <span className="ml-1 text-xs text-gray-500">⏳ 끝나지 않은 구간</span>}
      {row.provisional && <span className="ml-1 text-xs text-gray-500">⏳ 잠정</span>}
    </>
  );
}

export function IndicatorTable({ table, period, onPeriod, onMore, loading, error = null, switching = false }: {
  table: IndicatorTableResponse;
  period: IndicatorTablePeriod;
  onPeriod: (period: IndicatorTablePeriod) => void;
  onMore: () => void;
  /** 더 받는 중. */
  loading: boolean;
  /** 더 받기 실패 — 그동안 감시를 끊는다(같은 오류를 되풀이하지 않는다). */
  error?: string | null;
  /** 다른 단위의 표를 받는 중 — 앞 표를 흐리게 남긴다(단위 단추는 새 단위다). */
  switching?: boolean;
}) {
  const sentinel = useInfiniteScroll(onMore, table.hasMore && !loading && !switching && error === null);
  const year = table.rows[0]?.date.slice(0, 4) ?? null;
  const dateText = (date: string) => (date.slice(0, 4) === year ? date.slice(5) : date);

  return (
    <section data-testid="indicator-table" className="space-y-2">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-sm font-semibold text-gray-900">일자별</h3>
        <div role="group" aria-label="표 단위" className="inline-flex rounded border border-gray-300">
          {PERIODS.map(({ period: p, label }) => (
            <button key={p} type="button" aria-pressed={period === p} onClick={() => onPeriod(p)}
              className={`px-3 py-1 text-sm ${period === p ? "bg-gray-900 text-white" : "text-gray-700 hover:bg-gray-50"}`}>
              {label}
            </button>
          ))}
        </div>
        {table.seriesNote === "fx_fixing" && <span className="text-xs text-gray-500">고시 — 하루 한 값</span>}
        {switching && <span className="text-xs text-gray-500">불러오는 중…</span>}
      </div>
      {table.rows.length === 0 ? (
        <p className="rounded border border-gray-200 px-4 py-6 text-center text-sm text-gray-500">표시할 행이 없습니다.</p>
      ) : (
        <div aria-busy={switching} className={`overflow-x-auto rounded border border-gray-200 ${switching ? "opacity-50" : ""}`}>
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-200 text-gray-500">
                {COLUMNS.map((c) => (
                  <th key={c} scope="col" className={`px-2 py-2 font-medium ${c === "날짜" ? "text-left" : "text-right"}`}>{c}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row) => row.kind === "missing" ? (
                <tr key={`missing-${row.date}`} data-testid="table-missing" className="border-b border-gray-100 bg-gray-50">
                  <td colSpan={COLUMNS.length} className="px-2 py-1.5 text-gray-500">
                    {`결측 — ${row.date} ~ ${row.dateTo} 출처에 값 없음`}
                  </td>
                </tr>
              ) : (
                <tr key={row.date} data-testid="table-row" className="border-b border-gray-100">
                  <td className="whitespace-nowrap px-2 py-1.5 text-left tabular-nums text-gray-700">
                    {dateText(row.date)}<Marks row={row} />
                  </td>
                  <td className={CELL}>{value(row.open)}</td>
                  <td className={CELL}>{value(row.high)}</td>
                  <td className={CELL}>{value(row.low)}</td>
                  <td className={`${CELL} font-medium`}>{value(row.close)}</td>
                  <td className={`${CELL} ${tone(row.change)}`}>{changeText(row.change)}</td>
                  <td className={`${CELL} ${tone(row.changeRate)}`}>
                    {row.changeRate === null ? "—" : formatPercent(row.changeRate)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {error !== null && <p role="alert" className="text-xs text-amber-800">{error}</p>}
      {loading && <p className="text-xs text-gray-500">더 받는 중…</p>}
      {table.hasMore && <div ref={sentinel} aria-hidden="true" className="h-1" />}
    </section>
  );
}
