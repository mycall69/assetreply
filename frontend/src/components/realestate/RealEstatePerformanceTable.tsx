"use client";

/**
 * 부동산 월별 투자 성과 표 (T039) — 009 FR-017, FR-018, FR-020, FR-021, FR-026, FR-028, SC-010, ui-wireframes E5.
 *
 * - 열 11개(FR-028). 금액 열의 통화(KRW)는 열 이름 아래 줄이다(008 D4와 같은 자리)
 * - **적용 시세 칸은 두 줄** — 시세와 그 아래 "창·건수", 추정·잠정이면 글자로 덧붙인다(색만으로 전달하지 않는다, FR-017·FR-018)
 * - 그 달 평균은 거래가 없으면 "—", 시세 없음 달은 "시세 없음"과 평가액·투자 수익·수익률 "—"(0이 아니다, FR-026)
 * - 취득 비용은 **매입 행에만** — 합계와 그 아래 취득세(지방교육세·농어촌특별세 포함, 항목은 `title`)·중개 수수료(FR-020)
 * - 재산세는 7월·9월에 분납 차례, 7월 일괄이면 "(일괄)". 종부세는 12월. 다른 달은 **빈칸** — 0을 채우면 "안 냄"과 구별할 수 없다.
 *   계산하지 못한 해(`taxGaps`)의 7·9월 재산세·12월 종부세는 "계산 불가"(FR-021)
 * - 세금의 기준 시세(그해 6월)가 추정·잠정이면 세금 아래에 글자로, 칸의 `title`에 기준 시세·창·건수(FR-021)
 * - 최신순으로 한 번에 모두(20년이어도 240행 남짓). 표는 **내용 폭**이다 — 1440px에서 가로 스크롤이 없다(SC-010)
 *
 * 손익은 부호와 함께 쓴다(접근성). 금액은 서버의 문자열을 쉼표만 넣어 보인다(헌법 원칙 VI).
 */

import { formatMoney, formatPercent } from "@/lib/format";
import type { RealEstateAcquisition, RealEstateRow, RealEstateTax } from "@/lib/types";

const COLUMNS: readonly { name: string; unit: string | null; title?: string }[] = [
  { name: "월", unit: null },
  { name: "거래", unit: null, title: "그 달 거래 건수 — 해제된 거래는 뺍니다." },
  { name: "그 달 평균", unit: "KRW", title: "그 달 실거래 평균. 거래가 없으면 비웁니다." },
  { name: "적용 시세", unit: "KRW",
    title: "쓴 창·건수. 1개월보다 넓은 창은 추정, 최근 잠정 달이 들어가면 잠정입니다." },
  { name: "취득 비용", unit: "KRW", title: "매입한 달에만 — 취득세(지방교육세·농어촌특별세 포함)와 중개 수수료" },
  { name: "재산세", unit: "KRW", title: "낸 달에만 — 7월·9월에 나눠 내고, 소액이면 7월에 한 번에 냅니다." },
  { name: "종부세", unit: "KRW", title: "낸 달(12월)에만" },
  { name: "누적 비용", unit: "KRW" },
  { name: "평가액", unit: "KRW" },
  { name: "투자 수익", unit: "KRW" },
  { name: "수익률", unit: null },
];

const CELL = "whitespace-nowrap px-1.5 py-2 text-right align-top tabular-nums";
const SUB = "block text-[11px] text-gray-500";

const won = (value: string) => formatMoney(value, "KRW");
const orDash = (value: string | null, format: (v: string) => string) => (value === null ? "—" : format(value));

/**
 * 원 단위 정수 문자열의 합. **정수 연산(`BigInt`)**이라 IEEE 754를 거치지 않는다(헌법 원칙 VI). 서버가 준 세 항목을 표의 한 줄로
 * 묶어 보이기만 한다 — 계산 결과로 쓰지 않는다.
 */
function sumWon(...values: string[]): string {
  return values.reduce((total, value) => total + BigInt(value), BigInt(0)).toString();
}

/** 시세의 창·건수와 추정·잠정 — "3개월·41건 추정·잠정". */
function windowNote(window: number, trades: number, estimated: boolean, provisional: boolean): string {
  const flags = [estimated && "추정", provisional && "잠정"].filter(Boolean).join("·");
  return `${window}개월·${trades.toLocaleString("ko-KR")}건${flags === "" ? "" : ` ${flags}`}`;
}

function PriceCell({ row }: { row: RealEstateRow }) {
  if (row.price === null || row.window === null || row.windowTrades === null) {
    return <td className={CELL}>시세 없음</td>;
  }
  return (
    <td className={CELL}>
      {won(row.price)}
      <span className={SUB}>{windowNote(row.window, row.windowTrades, row.estimated, row.provisional)}</span>
    </td>
  );
}

function AcquisitionCell({ cost }: { cost: RealEstateAcquisition | null }) {
  if (cost === null) return <td className={CELL} />;
  const items = `취득세 ${won(cost.acquisitionTax)} · 지방교육세 ${won(cost.educationTax)} · 농어촌특별세 ${won(cost.ruralTax)}`;
  return (
    <td className={CELL}>
      {won(cost.total)}
      <span className={SUB} title={items}>
        취득세 {won(sumWon(cost.acquisitionTax, cost.educationTax, cost.ruralTax))}
      </span>
      <span className={SUB}>중개 {won(cost.brokerageFee)}</span>
    </td>
  );
}

/** 세금 칸. 내지 않은 달은 빈칸, 계산하지 못한 해의 납부 달은 "계산 불가"다. */
function TaxCell({ tax, gap, installment }: { tax: RealEstateTax | null; gap: boolean; installment: boolean }) {
  if (tax === null) return <td className={CELL}>{gap ? "계산 불가" : ""}</td>;
  const { basis } = tax;
  const flags = [basis.estimated && "추정", basis.provisional && "잠정"].filter(Boolean).join("·");
  const title = `${basis.month} 시세 ${won(basis.price)} · ${windowNote(basis.window, basis.windowTrades, false, false)}`;
  return (
    <td className={CELL} title={title}>
      {won(tax.amount)}
      {installment && ` (${tax.installment === "1/1" ? "일괄" : tax.installment})`}
      {flags !== "" && <span className={SUB}>6월 시세 {flags}</span>}
    </td>
  );
}

export function RealEstatePerformanceTable({ rows, taxGaps }: { rows: RealEstateRow[]; taxGaps: number[] }) {
  if (rows.length === 0) {
    return (
      <p className="rounded-lg border border-gray-200 px-4 py-8 text-center text-sm text-gray-500">
        표시할 행이 없습니다.
      </p>
    );
  }

  return (
    <div className="w-fit max-w-full overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-max text-xs">
        <thead>
          <tr className="border-b border-gray-200 text-xs text-gray-500">
            {COLUMNS.map((c, i) => (
              <th key={c.name} scope="col" title={c.title}
                className={`whitespace-nowrap px-1.5 py-2.5 align-top font-normal ${i < 1 ? "text-left" : "text-right"}`}>
                {c.name}
                {c.unit !== null && (
                  <>
                    {" "}
                    <span className="block text-gray-400">({c.unit})</span>
                  </>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const month = row.month.slice(5);
            const gap = taxGaps.includes(Number(row.month.slice(0, 4)));
            const negative = row.profit !== null && row.profit.startsWith("-");
            return (
              <tr key={row.month} className="border-b border-gray-100 last:border-0">
                <td className="whitespace-nowrap px-1.5 py-2 text-left align-top tabular-nums">{row.month}</td>
                <td className={CELL}>{row.trades.toLocaleString("ko-KR")}</td>
                <td className={CELL}>{orDash(row.monthAverage, won)}</td>
                <PriceCell row={row} />
                <AcquisitionCell cost={row.acquisition} />
                <TaxCell tax={row.propertyTax} gap={gap && (month === "07" || month === "09")} installment />
                <TaxCell tax={row.comprehensiveTax} gap={gap && month === "12"} installment={false} />
                <td className={CELL}>{won(row.cumulativeCost)}</td>
                <td className={CELL}>{orDash(row.value, won)}</td>
                <td className={`${CELL} ${negative ? "text-blue-700" : ""}`}>{orDash(row.profit, won)}</td>
                <td className={`${CELL} ${negative ? "text-blue-700" : ""}`}>{orDash(row.returnRate, formatPercent)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
