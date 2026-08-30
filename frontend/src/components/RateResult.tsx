/**
 * 조회 결과 카드 (T056, T057) — contracts/ui-sketches.md S1·S2.
 *
 * **`no_quote`일 때 주 결과 영역에 값을 넣지 않는다.** 직전 영업일 값은 시각적으로
 * 분리된 참고 영역에만 두고, 요청일의 값이 아님을 명시한다 (헌법 원칙 V, FR-018a/b).
 */

import { formatRate, unitLabel } from "@/lib/format";
import type { RateNoQuote, RateQuoted } from "@/lib/types";

export function RateResult({ result }: { result: RateQuoted | RateNoQuote }) {
  return (
    <section className="rounded-lg border border-gray-200 p-6">
      <header className="mb-4 text-sm text-gray-500">
        {result.currency} · {result.date}
      </header>

      {result.status === "quoted" ? (
        <QuotedBody result={result} />
      ) : (
        <NoQuoteBody result={result} />
      )}
    </section>
  );
}

const DERIVED_LABELS = [
  { key: "cashBuy", label: "현금 살 때" },
  { key: "cashSell", label: "현금 팔 때" },
  { key: "remitSend", label: "송금 보낼 때" },
  { key: "remitReceive", label: "송금 받을 때" },
] as const;

/** 비율 0.0018 → "0.18%" */
function toPercent(ratio: string): string {
  const n = Number(ratio) * 100;
  return `${n.toFixed(2).replace(/\.?0+$/, "")}%`;
}

function QuotedBody({ result }: { result: RateQuoted }) {
  return (
    <>
      <div data-testid="primary-result">
        <p className="text-sm text-gray-500">매매기준율</p>
        <p className="text-3xl font-semibold tabular-nums">
          {formatRate(result.baseRate)}{" "}
          <span className="text-base font-normal text-gray-500">
            {unitLabel(result.quoteUnit)}
          </span>
        </p>
      </div>

      <dl
        data-testid="derived-rates"
        className="mt-6 grid grid-cols-2 gap-x-8 gap-y-3 border-t border-gray-200 pt-6"
      >
        {DERIVED_LABELS.map(({ key, label }) => (
          <div key={key} className="flex justify-between">
            <dt className="text-sm text-gray-500">{label}</dt>
            <dd className="tabular-nums">{formatRate(result.derived[key])}</dd>
          </div>
        ))}
      </dl>

      {/* FR-026a: 어떤 가정 위의 결과인지 드러나야 한다 */}
      <div className="mt-6 rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
        ⓘ 현재 설정된 스프레드를 이 날짜에 적용한 결과입니다. 현금{" "}
        {toPercent(result.appliedSpread.cashBuy)} · 송금{" "}
        {toPercent(result.appliedSpread.remitSend)}
      </div>

      <p className="mt-4 text-xs text-gray-400">출처: {result.source}</p>
    </>
  );
}

function NoQuoteBody({ result }: { result: RateNoQuote }) {
  return (
    <>
      {/* 주 결과 — 숫자를 넣지 않는다 */}
      <div data-testid="primary-result" className="py-4">
        <p className="text-lg text-gray-700">{result.message}</p>
      </div>

      {result.reference && (
        <>
          <div className="my-6 border-t border-dashed border-gray-300 pt-1 text-center">
            <span className="bg-white px-3 text-xs text-gray-400">참고 정보</span>
          </div>
          <div
            data-testid="reference-block"
            className="rounded-md border border-gray-200 bg-gray-50 p-4"
          >
            <p className="text-sm text-gray-500">직전 영업일 {result.reference.date}</p>
            <p className="mt-1 text-xl font-medium tabular-nums">
              {formatRate(result.reference.baseRate)}{" "}
              <span className="text-sm font-normal text-gray-500">
                {unitLabel(result.reference.quoteUnit)}
              </span>
            </p>
            <p className="mt-3 text-sm text-amber-700">⚠ {result.reference.note}</p>
          </div>
        </>
      )}
    </>
  );
}
