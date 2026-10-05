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

import { formatMoneyWithSymbol, formatPercent, shiftDecimal } from "@/lib/format";
import type { RealEstateSimulationResponse } from "@/lib/types";

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
  const negative = summary.profit !== null && summary.profit.trimStart().startsWith("-");
  const emphasis = summary.profit === null ? undefined : negative ? "loss" : "gain";
  const valueFlags = [summary.estimated && "추정", summary.provisional && "잠정"].filter(Boolean).join(" · ");
  const buyWindow = condition.buyPriceWindow;

  const basis = [
    `${complex.name} ${area.label}`,
    `${condition.buyDate} 매입`,
    `보유세 기준 시세의 ${ratioPercent(condition.holdingTaxBaseRatio)}`,
    ...condition.assumptions,
    ...(condition.buyPriceSource === "input" ? ["매입가 직접 입력"] : []),
  ];

  return (
    <section className="rounded-lg border border-gray-200">
      <div className="grid gap-px bg-gray-200 sm:grid-cols-3 xl:grid-cols-6">
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
        <Cell label="투자 수익" value={summary.profit === null ? "—" : won(summary.profit)} emphasis={emphasis} />
        <Cell label="수익률" value={summary.returnRate === null ? "—" : formatPercent(summary.returnRate)}
          emphasis={emphasis} />
      </div>

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {/* 어느 날짜까지의 결과인지 알 수 없으면 오늘까지로 읽는다. */}
        <span className="tabular-nums">{summary.asOf}</span> 기준
        {basis.map((item) => (
          <span key={item}> · {item}</span>
        ))}
      </p>
    </section>
  );
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
