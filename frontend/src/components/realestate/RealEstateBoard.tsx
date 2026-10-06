"use client";

/**
 * 부동산 성과 보드 (T039) — 009 FR-006, FR-017, FR-018, FR-026, FR-029, FR-030, ui-wireframes E4.
 *
 * **부동산 전용 보드**다 — 칸이 여섯이라 `PerformanceBoard`(원금·수익·수익률)를 늘리지 않는다(research R9-10). 금액·수익률은
 * `PerformanceBoard`와 **같은 형식 함수**다 — 기호가 숫자 앞(`₩2,023,166,667`), 손실은 `-₩…`, 수익률은 부호와 함께(FR-029).
 * 손익을 색만으로 구별하지 않는다(접근성).
 *
 * - 매입가 칸 아래: 직접 넣었으면 "직접 입력", 아니면 쓴 창·건수(넓은 창이면 "추정") — 시세로 산 사실을 감추면 실제 매입가로 읽는다
 * - 평가액 칸 아래: 쓴 창·건수와 추정·잠정(FR-017·FR-018). 지금 시세가 없으면 0이 아니라 "—"(FR-026 — 사유는 아래 안내 줄)
 * - 기준 줄: 어느 날짜까지 · 단지 · 평형 · 매입일 · 가정(보유세 기준 비율과 서버의 가정) — 가정이 보이지 않으면 실제 공시가격·단독
 *   명의로 계산한 결과로 읽는다(FR-030)
 */

import { ComplexLink } from "@/components/realestate/ComplexLink";
import { formatMoneyWithSymbol, formatPercent, shiftDecimal } from "@/lib/format";
import type { RealEstateSaleCost, RealEstateSimulationResponse } from "@/lib/types";

export type RealEstateBoardResult = Omit<RealEstateSimulationResponse, "rows">;

const won = (value: string) => formatMoneyWithSymbol(value, "KRW");

/** 시세의 창과 건수 — "그 달 시세 · 6건", "3개월 평균 · 41건"(FR-017). */
export function windowText(months: number, trades: number): string {
  const count = `${trades.toLocaleString("ko-KR")}건`;
  return months === 1 ? `그 달 시세 · ${count}` : `${months}개월 평균 · ${count}`;
}

/** 비율 `"0.600000"` → `60%`, `"0.655000"` → `65.5%`. 문자열로만 옮긴다(헌법 원칙 VI). */
export function ratioPercent(ratio: string): string {
  const shifted = shiftDecimal(ratio, 2);
  const trimmed = shifted.includes(".") ? shifted.replace(/0+$/, "").replace(/\.$/, "") : shifted;
  return `${trimmed}%`;
}

export function RealEstateBoard({ result }: { result: RealEstateBoardResult }) {
  const { complex, area, condition, acquisition, summary } = result;
  // 010 반복 5(FR-031) — 매도비용을 뺀 값을 알면 투자 수익·수익률 칸은 그 값이다(보유 중 값은 함께 보인다).
  const sale = summary.saleCost;
  const after = sale !== undefined && summary.profitAfterSale != null && summary.returnRateAfterSale != null
    ? { profit: summary.profitAfterSale, rate: summary.returnRateAfterSale }
    : null;
  const shownProfit = after?.profit ?? summary.profit;
  const shownRate = after?.rate ?? summary.returnRate;
  const negative = shownProfit !== null && shownProfit.trimStart().startsWith("-");
  const emphasis = shownProfit === null ? undefined : negative ? "loss" : "gain";
  const holding = (text: string | null) => (sale === undefined ? []
    : after !== null ? ["매도비용을 뺀 값", text === null ? null : `보유 중 ${text}`]
      : ["매도 세금을 모름 — 보유 중 값"]);
  const valueFlags = [summary.estimated && "추정", summary.provisional && "잠정"].filter(Boolean).join(" · ");
  const buyWindow = condition.buyPriceWindow;

  const basis = [
    `${condition.buyDate} 매입`,
    `보유세 기준 시세의 ${ratioPercent(condition.holdingTaxBaseRatio)}`,
    ...condition.assumptions,
    ...(condition.buyPriceSource === "input" ? ["매입가 직접 입력"] : []),
  ];
  // 매도비용의 가정 — 한 줄로 밝힌다(FR-031). 보드가 월별 표의 마지막 행과 다른 까닭이 여기 있다.
  const saleBasis = sale === undefined ? null
    : `매도비용: 1세대 1주택 · 부부 5:5 · 거주 기간 = 보유 × ${ratioPercent(condition.residenceRatio ?? "1")}`
      + " · 기준일에 평가액으로 판다고 가정한 값 — 월별 표는 보유 중 평가";

  return (
    <section className="rounded-lg border border-gray-200">
      <div className={`grid gap-px bg-gray-200 sm:grid-cols-3 ${sale !== undefined ? "xl:grid-cols-7" : "xl:grid-cols-6"}`}>
        <Cell label="매입가" value={won(condition.buyPrice)}
          notes={[condition.buyPriceSource === "input" ? "직접 입력"
            : buyWindow === null ? null
              : `${windowText(buyWindow.months, buyWindow.trades)}${buyWindow.estimated ? " · 추정" : ""}`]} />
        <Cell label="투입 금액" value={won(summary.invested)}
          notes={["매입가 + 취득 비용", won(acquisition.total)]} />
        <Cell label="누적 보유세" value={won(summary.holdingTaxTotal)}
          notes={[`재산세 ${won(summary.propertyTaxTotal)}`, `종부세 ${won(summary.comprehensiveTaxTotal)}`]} />
        <Cell label="평가액(지금 시세)" value={summary.value === null ? "—" : won(summary.value)}
          notes={summary.value === null ? ["지금 시세 없음"] : [
            summary.valueWindow === null ? null : windowText(summary.valueWindow.months, summary.valueWindow.trades),
            valueFlags === "" ? null : valueFlags,
          ]} />
        {sale !== undefined && (
          <Cell label="매도비용" value={sale.total === null ? "—" : won(`-${sale.total}`)} notes={saleNotes(sale)} />
        )}
        <Cell label="투자 수익" value={shownProfit === null ? "—" : won(shownProfit)} emphasis={emphasis}
          notes={holding(summary.profit === null ? null : won(summary.profit))} />
        <Cell label="수익률" value={shownRate === null ? "—" : formatPercent(shownRate)} emphasis={emphasis}
          notes={holding(summary.returnRate === null ? null : formatPercent(summary.returnRate))} />
      </div>

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {/* 어느 날짜까지의 결과인지 알 수 없으면 오늘까지로 읽는다. */}
        <span className="tabular-nums">{summary.asOf}</span> 기준 ·{" "}
        {/* 010 FR-029 — 단지 이름은 Npay 부동산 단지 화면(번호를 모르는 동안·못 찾으면 네이버 검색 — FR-026) 링크다. */}
        <ComplexLink complexId={complex.complexId} name={complex.name} umdName={complex.umdName} />{" "}
        {area.label}
        {basis.map((item) => (
          <span key={item}> · {item}</span>
        ))}
      </p>
      {saleBasis !== null && <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">{saleBasis}</p>}
    </section>
  );
}

/** 매도비용 칸의 내역 — 중개 보수, 양도소득세(지방소득세 포함)와 판정·장특공·보유·거주 연수(FR-031). */
function saleNotes(sale: RealEstateSaleCost): string[] {
  const lines = [`중개 보수 ${won(sale.brokerage)}`];
  if (sale.incomeTax === null || sale.localTax === null) {
    lines.push("세금 — 규칙 표 밖(2023-01-01 앞)");
    return lines;
  }
  const tax = (BigInt(sale.incomeTax) + BigInt(sale.localTax)).toString();
  lines.push(`양도소득세 ${won(tax)} (지방소득세 포함)`);
  const years = `보유 ${sale.holdingYears}년 · 거주 ${sale.residenceYears}년`;
  const ltsd = sale.ltsdRate === null ? "" : `장특공 ${ratioPercent(sale.ltsdRate)} · `;
  if (sale.kind === "exempt") lines.push("비과세(12억 이하)");
  else if (sale.kind === "high_price") lines.push(`고가주택(12억 초과분) · ${ltsd}${years}`);
  else if (sale.kind === "taxed") lines.push(`비과세 요건 밖(거주 2년 미만) · ${ltsd}${years}`);
  else if (sale.kind === "short_term") lines.push(`단기 보유 — 세율 ${sale.holdingYears < 1 ? "70%" : "60%"}`);
  else if (sale.kind === "no_gain") lines.push("양도차익 없음");
  return lines;
}

function Cell({
  label,
  value,
  notes = [],
  emphasis,
}: {
  label: string;
  value: string;
  notes?: (string | null)[];
  emphasis?: "gain" | "loss";
}) {
  return (
    <div role="group" aria-label={label} className="bg-white px-4 py-3">
      <p aria-hidden="true" className="text-xs text-gray-500">{label}</p>
      <p className={`mt-1 text-xl font-semibold tabular-nums ${
        emphasis === "loss" ? "text-blue-700" : emphasis === "gain" ? "text-red-700" : "text-gray-900"}`}>
        {value}
      </p>
      {notes.filter((n): n is string => n !== null).map((note) => (
        <p key={note} className="text-xs tabular-nums text-gray-500">{note}</p>
      ))}
    </div>
  );
}
