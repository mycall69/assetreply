"use client";

/**
 * 성과 표 (T043, T048) — 005 FR-024~030, contracts/ui-wireframes.md W4.
 *
 * **월 행의 배당 칸은 비어 있다**(FR-026). 0을 넣으면 "배당이 0원"과 "배당이 없음"을
 * 구별할 수 없다 — 002·003·004가 세운 규약과 같다.
 *
 * **스크롤로 이어 본다**(FR-029). `더 보기` 버튼을 두지 않는다. 004가 세운 방식이며,
 * 감시 지점이 처음부터 보이면 스크롤 없이도 시작된다.
 *
 * 손익을 **색만으로 구별하지 않는다.** 부호를 함께 쓴다 (접근성).
 *
 * 006 FR-066~069 — 해외 종목은 **열마다 통화가 정해져 있다**(ui-wireframes W8). 예수금·세금·수수료·잔고·
 * 배당금 총액은 종목 통화, 잔고 괄호는 KRW, 투자금은 입력한 원금 통화, 투자 수익·수익율은 KRW 기준이다.
 * 1440px에서 열 15개가 가로 스크롤 없이 들어가도록 칸을 촘촘하게 두고, 머리글의 통화는 열 이름 아래 줄에 둔다
 * (research R6-26 — 한 줄이면 표가 1,365px로 칸 1,166px를 넘었다).
 */

import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";
import {
  formatDividend,
  formatMoney,
  formatPercent,
  formatRate,
  formatYield,
} from "@/lib/format";
import type { SimulationRow, SimulationSummary } from "@/lib/types";

// 006 FR-059 — 배당 소득세(배당락 행)와 매매 수수료(매수 행). FR-067 — 배당금 총액(배당락 행).
const COLUMNS = [
  "날짜", "시작가", "주당 배당금", "배당율", "배당금 총액", "배당 소득세", "구매 주식수",
  "매매 수수료", "보유 주식", "예수금", "투자금", "잔고", "투자 수익", "수익율",
] as const;

/**
 * 종목 통화 금액 열 — 해외 종목이면 머리글에 종목 통화를 붙인다(006 FR-066). 세금·수수료도 예수금에서
 * 빠지는 돈이라 예수금과 같은 통화여야 예수금 변화를 설명할 수 있다.
 */
const STOCK_COLUMNS = ["시작가", "주당 배당금", "배당금 총액", "배당 소득세", "매매 수수료", "예수금"];

/** 칸 여백 — 열 15개가 1440px에 들어가도록 좁힌다 (006 FR-069). */
const CELL = "px-1.5 py-2 text-right tabular-nums";

/** 외화 종목에만 붙는 열 (FR-041c). */
const FX_COLUMN = "환율";

export function PerformanceTable({
  rows,
  currency,
  stockCurrency,
  summary,
  hasMore,
  loadingMore = false,
  loadError = null,
  onLoadMore,
}: {
  rows: SimulationRow[];
  /** 입력한 원금 통화 — 투자금 열의 통화다. */
  currency: string;
  /** 종목의 거래 통화. KRW가 아니면 열마다 통화를 붙이고 잔고에 KRW 괄호가 붙는다 (006 FR-066). */
  stockCurrency?: string;
  /**
   * 요약. **기준일 안내를 여기서도 보이기 위해서다**(FR-014b, SC-027).
   *
   * 보드에만 두면 표를 보던 사용자는 마지막 행을 오늘까지의 결과로 읽는다 —
   * 상장폐지는 대개 큰 손실이라 그 오독의 대가가 크다.
   */
  summary?: SimulationSummary;
  hasMore: boolean;
  loadingMore?: boolean;
  loadError?: string | null;
  onLoadMore: () => void;
}) {
  // 실패한 동안에는 감시를 끊는다. 즉시 다시 관찰하면 같은 오류를 무한히 반복한다.
  const open = hasMore && !loadingMore && loadError === null;
  const sentinel = useInfiniteScroll(onLoadMore, open);

  // 외화 종목일 때만 환율 열을 둔다. 늘 두면 국내 종목에서 빈 열이 남는다.
  const showFx = rows.some((r) => r.fxRate !== undefined);

  // **한 행에 통화가 섞인다**(006 FR-066). 표기하지 않으면 사용자가 같은 단위로 읽어 잔고와 예수금을
  // 더해 본다. 국내 종목은 모두 KRW라 붙이지 않는다 — 원금 통화가 종목 통화와 같아도(달러 원금·미국
  // 종목) 투자 수익은 KRW라 붙인다.
  const stockCcy = stockCurrency ?? currency;
  const foreign = stockCcy !== "KRW";
  const unitOf = (column: string): string | null => {
    if (!foreign) return null;
    if (STOCK_COLUMNS.includes(column)) return stockCcy;
    if (column === "투자금") return currency;
    if (column === "잔고") return `${stockCcy} · KRW`;
    if (column === "투자 수익") return "KRW";
    if (column === "수익율") return "KRW 기준";
    return null;
  };

  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  const cutOff = summary !== undefined && !summary.isFinal;

  return (
    <div className="rounded-lg border border-gray-200">
      {cutOff && (
        // FR-014b, SC-027 — 보드에만 두면 표를 보던 사용자는 마지막 행을 오늘까지의
        // 결과로 읽는다. 상장폐지는 대개 큰 손실이라 그 오독의 대가가 크다.
        <p
          data-testid="table-asof"
          className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800"
        >
          ⚠ <span className="tabular-nums">{summary.asOf}</span> 이후 시세가
          없습니다. 아래 행은 그 날짜까지의 결과입니다.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              {[...COLUMNS, ...(showFx ? [FX_COLUMN] : [])].map((c, i) => {
                const unit = unitOf(c);
                return (
                  <th
                    key={c}
                    scope="col"
                    className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${
                      i === 0 ? "text-left" : "text-right"
                    }`}
                  >
                    {c}
                    {/* 통화는 열 이름 아래 줄 — 한 줄이면 1440px에서 오른쪽 열이 잘린다 (R6-26). */}
                    {unit !== null && (
                      <>
                        {" "}
                        <span className="block text-gray-400">({unit})</span>
                      </>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={`${row.date}:${row.kind}`}
                data-kind={row.kind}
                className={`border-b border-gray-100 last:border-0 ${
                  row.kind === "dividend"
                    ? "bg-amber-50/40"
                    : row.kind === "reinvest" ? "bg-emerald-50/40" : ""
                }`}
              >
                <td className="whitespace-nowrap px-1.5 py-2 tabular-nums">
                  {row.date}
                  {row.kind === "dividend" && (
                    <span title="배당락일" className="ml-1 text-amber-700">
                      ◆
                    </span>
                  )}
                  {row.kind === "reinvest" && (
                    // 006 FR-058 — 배당락 뒤 2번째 거래일의 재투자 매수. 색만으로 전달하지 않는다.
                    <span title="배당 재투자" className="ml-1 text-xs text-emerald-700">
                      ⟳ 재투자
                    </span>
                  )}
                </td>
                <td className={CELL}>{formatRate(row.openPrice)}</td>
                {/* 월 행은 키 자체가 없다 — 빈 칸이 "배당 없음"을 뜻한다. */}
                <td className={CELL}>
                  {/* 006 FR-057 — 종목 통화 값이다. 소수 3자리. */}
                  {row.dividendPerShare !== undefined
                    ? formatDividend(row.dividendPerShare)
                    : ""}
                </td>
                <td className={CELL}>
                  {row.dividendYield !== undefined
                    ? formatYield(row.dividendYield)
                    : ""}
                </td>
                <td className={`whitespace-nowrap ${CELL}`}>
                  {/* 006 FR-067 — 세전과 괄호에 세후. 실제로 받은 돈을 곱셈으로 다시 구하지 않게 한다. */}
                  {row.dividendTotal !== undefined && (
                    <>
                      {formatMoney(row.dividendTotal, stockCcy)}
                      {row.dividendTotalNet !== undefined && (
                        <>
                          {" "}
                          <span className="text-gray-500">
                            ({formatMoney(row.dividendTotalNet, stockCcy)})
                          </span>
                        </>
                      )}
                    </>
                  )}
                </td>
                <td className={CELL}>
                  {row.dividendTax !== undefined ? formatMoney(row.dividendTax, stockCcy) : ""}
                </td>
                <td className={CELL}>{row.boughtShares}</td>
                <td className={CELL}>
                  {row.tradeFee !== undefined ? formatMoney(row.tradeFee, stockCcy) : ""}
                </td>
                <td className={CELL}>{row.heldShares}</td>
                <td className={CELL}>{formatMoney(row.cash, stockCcy)}</td>
                <td className={CELL}>{formatMoney(row.principal, currency)}</td>
                <td className={`whitespace-nowrap font-medium ${CELL}`}>
                  {formatMoney(row.balance, stockCcy)}
                  {/* 006 FR-066 — 해외 종목이면 괄호에 KRW 평가. 국내 종목은 붙이지 않는다. */}
                  {row.balanceKrw !== undefined && (
                    <>
                      {" "}
                      <span className="font-normal text-gray-500">
                        ({formatMoney(row.balanceKrw, "KRW")})
                      </span>
                    </>
                  )}
                </td>
                {/* 006 FR-068 — 원금 통화와 관계없이 KRW 기준이다. */}
                <td className={CELL}>{formatMoney(row.profit, "KRW")}</td>
                <td className={CELL}>{formatPercent(row.returnRate)}</td>
                {showFx && (
                  <td className={`whitespace-nowrap ${CELL}`}>
                    {row.fxRate !== undefined ? formatRate(row.fxRate) : ""}
                    {/*
                      FR-041c — 쓴 환율의 날짜가 기준일과 다를 수 있다. 주식 거래일과
                      환율 고시일은 일치하지 않는다. **기호만으로 전달하지 않는다.**
                    */}
                    {row.fxRateDate !== undefined && row.fxRateDate !== row.date && (
                      <span
                        role="img"
                        className="ml-1"
                        title={`${row.date}에 환율 고시가 없어 ${row.fxRateDate} 값을 썼습니다`}
                        aria-label={`${row.date}에 환율 고시가 없어 ${row.fxRateDate} 값을 썼습니다`}
                      >
                        📅
                      </span>
                    )}
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 이어 보기 상태 — 004의 방식. `더 보기` 버튼이 없는 만큼 상태를 말로 알린다. */}
      <div className="flex items-center justify-center gap-3 border-t border-gray-100 px-4 py-3 text-xs">
        <span role="status" aria-live="polite" className="text-gray-500">
          {loadError
            ? loadError
            : loadingMore
              ? "⟳ 불러오는 중…"
              : !hasMore
                ? `${rows.at(-1)?.date ?? "처음"}까지 모두 표시했습니다`
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

      {hasMore && loadError === null && (
        <div ref={sentinel} data-testid="scroll-sentinel" aria-hidden="true" className="h-px" />
      )}
    </div>
  );
}
