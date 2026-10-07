"use client";

/**
 * 성과 보드 (T042, T078, T099) — 005 FR-031, FR-032, FR-014b, FR-041.
 * contracts/ui-wireframes.md W2. 006 FR-054 — 원금·수익에 원금 통화의 기호. 007 FR-042a(반복 2026-10-04) — 기호는
 * 숫자 앞이다(`₩10,000,000`, `$10,000 (₩13,520,000)`, `-₩5,446`).
 *
 * **기준 구간을 함께 쓴다.** 계산의 마지막 날이 오늘이 아니면(상장폐지·거래정지)
 * 그 사실이 드러나야 한다 — 알리지 않으면 사용자는 보드를 **오늘까지의 결과**로
 * 읽는다. 상장폐지는 대개 큰 손실인데 화면에는 폐지 직전의 수익률이 남는다.
 *
 * **기준 통화를 밝힌다**(FR-041). 밝히지 않으면 사용자가 어느 쪽을 보고 있는지 모른다.
 *
 * 손익을 **색만으로 구별하지 않는다.** 부호를 함께 쓴다 (접근성).
 *
 * 006 FR-068 — 투자 수익·수익률은 **원금 통화와 관계없이 KRW**다. 달러 원금만 달러 기준이면 이력
 * 비교에서 원화 원금 실행과 다른 기준의 수익률이 나란히 놓인다. 투자 원금은 입력한 통화로 보이고,
 * 원화가 아니면 괄호에 KRW 값(첫 매수일 매매기준율로 평가 — 수익률의 분모)을 붙인다(W8).
 *
 * 010 반복 4(FR-030) — 주식은 **투자 원금 · 매도 수수료/세금 · 투자 수익 · 수익률** 넷이다. 기준일에 모두 판다고 가정한 비용을
 * 투자 수익·수익률에서 빼고, 보유 중 값을 칸 안에 함께 둔다 — 보드가 표의 마지막 행과 다른 까닭이 보여야 한다. 세율 표 밖이면 세금을
 * 비우고(—) 보유 중 값을 그대로 보인다(0을 빼지 않는다). `saleCost`가 없으면(가상자산 등) 세 칸이다.
 *
 * 012 US5(FR-018) — `totalKrw`가 있으면 투자 원금 다음에 **현재 잔고**(기준일의 원화 총자산 — 잔고 + 예수금, 매도 비용 전)를 둔다. 주식 다섯 칸, 가상자산
 * 네 칸이다. 서버 값을 그린다 — 원금 + 수익을 더하지 않는다(헌법 원칙 VI). 표의 잔고 열(보유 평가액)과 다른 까닭이 보이게 "잔고 + 예수금"을 적는다. 잔고는
 * 손익이 아니라 손익 색을 쓰지 않는다. 같은 부품을 쓰는 예금 보드에는 `totalKrw`가 없어 칸이 없다.
 */

import { formatMoneyWithSymbol, formatPercent, formatRate } from "@/lib/format";
import type { ExchangeInfo, SaleCost, SimulationSummary } from "@/lib/types";

export function PerformanceBoard({
  summary,
  currency,
  exchange,
  notes = [],
  notFinalNotice = true,
}: {
  summary: SimulationSummary;
  /** 계산이 오늘 전에 끝났다는 시세 기준의 안내를 보일지. 예금(008)은 멈춘 사유(빈 금리 달)를 따로 말한다. */
  notFinalNotice?: boolean;
  /** 기준 줄에 덧붙일 말 — 가상자산의 매수일·수수료(007 ui-wireframes C3). */
  notes?: string[];
  /** 입력한 원금 통화 — 투자 원금 칸의 통화다. 수익의 기준은 KRW다. */
  currency: string;
  exchange?: ExchangeInfo;
}) {
  const sale = summary.saleCost;
  // 매도 비용을 뺀 값을 아는지 — 세율 표 밖이면 보유 중 값을 보인다.
  const after = sale !== undefined && summary.profitAfterSale != null && summary.returnRateAfterSale != null
    ? { profit: summary.profitAfterSale, rate: summary.returnRateAfterSale }
    : null;
  const shownProfit = after?.profit ?? summary.profit;
  const negative = shownProfit.trimStart().startsWith("-");
  const holdingNote = sale === undefined ? null : after !== null ? "보유 중" : "매도 세금을 모름 — 보유 중 값";
  const columns = 3 + (sale !== undefined ? 1 : 0) + (summary.totalKrw !== undefined ? 1 : 0);

  return (
    <section className="rounded-lg border border-gray-200">
      <div className={`grid gap-px bg-gray-200 ${GRID_COLUMNS[columns]}`}>
        <Cell label="투자 원금">
          {formatMoneyWithSymbol(summary.principal, currency)}
          {currency !== "KRW" && summary.principalKrw !== undefined && (
            <>
              {" "}
              <span className="text-base font-normal text-gray-500">
                ({formatMoneyWithSymbol(summary.principalKrw, "KRW")})
              </span>
            </>
          )}
        </Cell>
        {summary.totalKrw !== undefined && (
          <Cell label="현재 잔고" notes={["잔고 + 예수금"]}>
            {formatMoneyWithSymbol(summary.totalKrw, "KRW")}
          </Cell>
        )}
        {sale !== undefined && (
          <Cell label="매도 수수료/세금" notes={saleNotes(sale)}>
            {sale.total === null ? "—" : formatMoneyWithSymbol(`-${sale.total}`, "KRW")}
          </Cell>
        )}
        <Cell label="투자 수익" emphasis={negative ? "loss" : "gain"}
          notes={holdingNote === null ? [] : after !== null
            ? ["매도 비용을 뺀 값", `${holdingNote} ${formatMoneyWithSymbol(summary.profit, "KRW")}`]
            : [holdingNote]}>
          {formatMoneyWithSymbol(shownProfit, "KRW")}
        </Cell>
        <Cell label="수익률" emphasis={negative ? "loss" : "gain"}
          notes={holdingNote === null ? [] : after !== null
            ? ["매도 비용을 뺀 값", `${holdingNote} ${formatPercent(summary.returnRate)}`]
            : [holdingNote]}>
          {formatPercent(after?.rate ?? summary.returnRate)}
        </Cell>
      </div>

      <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
        {/* FR-031 — 어느 날짜까지의 결과인지 알 수 없으면 오늘까지로 읽는다. */}
        <span className="tabular-nums">{summary.asOf}</span> 기준 ·{" "}
        {/* 006 FR-068 — 원금 통화와 관계없이 KRW다. */}
        <span>KRW 기준</span>
        {notes.map((note) => (
          <span key={note}> · {note}</span>
        ))}
        {sale !== undefined && <span> · 매도 수수료·세금은 기준일에 모두 판다고 가정한 값 — 일자별 표는 보유 중 평가</span>}
      </p>

      {!summary.isFinal && notFinalNotice && (
        // FR-014b — 계산의 마지막 날이 오늘이 아니다. 알리지 않으면 폐지 직전
        // 수익률을 오늘 값으로 읽는다.
        <p
          role="status"
          className="border-t border-amber-200 bg-amber-50 px-4 py-2 text-xs text-amber-800"
        >
          ⚠ {summary.asOf} 이후 시세가 없습니다. 그 날짜까지의 결과입니다.
        </p>
      )}

      {exchange !== undefined && (
        // FR-021, FR-022 — 적용된 환율과 그 날짜가 드러나야 한다. 투자 시작일에
        // 고시가 없었다면 날짜가 다를 수 있다.
        <p className="border-t border-gray-100 px-4 py-2 text-xs text-gray-500">
          환전 <span className="tabular-nums">{exchange.rateDate}</span> 현금 살 때{" "}
          <span className="tabular-nums">{formatRate(exchange.rate)}</span>
          <span className="ml-1">
            (스프레드 {formatPercent(exchange.spreadDiscount, 0).replace("+", "")} 우대)
          </span>
        </p>
      )}
    </section>
  );
}

/**
 * 양도차익의 구성 두 줄 — "매도금액 − 취득가 − 수수료"와 취득가 설명(012 US6, contracts/ui-wireframes.md F10). 세 값 가운데 하나라도 없으면(국내·US6 전 응답)
 * 그리지 않는다. 적립식 보드도 쓴다 — 설명 줄만 다르다.
 */
export function gainBreakdown(sale: SaleCost, explanation: string): string[] {
  const { saleKrw, acquisitionKrw, feesKrw } = sale;
  if (saleKrw == null || acquisitionKrw == null || feesKrw == null) return [];
  const won = (v: string) => formatMoneyWithSymbol(v, "KRW");
  return [`매도금액 ${won(saleKrw)} − 취득가 ${won(acquisitionKrw)} − 수수료 ${won(feesKrw)}`, explanation];
}

/** 칸 수 → 격자 열(Tailwind는 글자 그대로의 클래스 이름만 만든다). */
const GRID_COLUMNS: Record<number, string> = { 3: "sm:grid-cols-3", 4: "sm:grid-cols-4", 5: "sm:grid-cols-5" };

/** 매도 칸의 내역 — 수수료, 세금(국내 증권거래세 또는 해외 양도소득세와 차익·공제), 표 밖이면 사유. */
function saleNotes(sale: SaleCost): string[] {
  const won = (v: string) => formatMoneyWithSymbol(v, "KRW");
  const rate = (v: string | null, digits: number) => (v === null ? "" : `${formatPercent(v, digits).replace("+", "")} `);
  const lines = [`수수료 ${won(sale.fee)}`];
  if (sale.taxKind === "transaction_tax" && sale.tax !== null) {
    lines.push(`증권거래세 ${rate(sale.taxRate, 2)}${won(sale.tax)}`);
  } else if (sale.taxKind === "capital_gains_tax" && sale.tax !== null) {
    lines.push(`양도소득세 ${rate(sale.taxRate, 0)}${won(sale.tax)}`);
    // 012 US6(FR-019) — 차익이 "현재 잔고 − 원금"보다 작은 까닭이 보이게 구성을 적는다. 서버 값을 그린다(빼지 않는다).
    lines.push(...gainBreakdown(sale, "취득가는 모든 매수(배당 재투자 포함) · 예수금은 팔지 않음"));
    if (sale.gain !== null && sale.deduction !== null) lines.push(`차익 ${won(sale.gain)} − 공제 ${won(sale.deduction)}`);
  } else {
    lines.push("세금 — 세율 표 밖(2023-01-01 앞)");
  }
  // 011 FR-037 — 세율·공제는 법령 표가 아니라 사용자가 바꿀 수 있는 설정값이다. 기존 문장은 그대로 두고 끝에 더한다.
  lines.push("세율·공제: 설정값(설정 > 주식 매도 세금)");
  return lines;
}

function Cell({
  label,
  children,
  emphasis,
  notes = [],
}: {
  label: string;
  children: React.ReactNode;
  emphasis?: "gain" | "loss";
  /** 값 아래의 작은 줄 — 매도 내역, 보유 중 값. */
  notes?: string[];
}) {
  return (
    <div className="bg-white px-4 py-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p
        className={`mt-1 text-xl font-semibold tabular-nums ${
          emphasis === "loss"
            ? "text-blue-700"
            : emphasis === "gain"
              ? "text-red-700"
              : "text-gray-900"
        }`}
      >
        {children}
      </p>
      {notes.map((note) => (
        <p key={note} className="mt-0.5 text-xs text-gray-500 tabular-nums">{note}</p>
      ))}
    </div>
  );
}
