/**
 * 지표 화면 머리 (014 T060) — FR-010, FR-015, FR-018, FR-019, contracts D3.
 *
 * 머리 값은 대시보드와 **같은 스토어**의 카드 값이다 — 다른 경로로 받으면 같은 지표의 값이 두 화면에서 다르다(FR-010 실패 양상).
 * 저장된 기간·출처·마지막 수집, 그리고 계열 주석(선물 근월물·환율의 고시 계열)과 수집 상태(최근 구간 받는 중·이어 받기 실패)를 보인다.
 */
import { NOTE_TEXT, previousText, stateText } from "@/components/dashboard/QuoteStateLine";
import { formatPercent, formatRate } from "@/lib/format";
import { KST_ZONE, formatZonedTime } from "@/lib/kstClock";
import type { DashboardIndicator, IndicatorSeriesResponse } from "@/lib/types";

export const FAILURE_LABELS: Record<string, string> = {
  rate_limited: "출처 응답 제한",
  connection: "연결 실패",
  blocked: "출처가 막음",
  invalid_body: "출처 응답을 읽지 못함",
  not_found: "출처에 없음",
  // 환율 그래프 — 외환 수집(001)이 실패했다. 문구는 외환 수집 기록의 것이다(반복 2026-10-10, FR-018)
  fx_collection: "외환 수집 실패",
};

export function failureLabel(kind: string | null | undefined): string {
  return (kind && FAILURE_LABELS[kind]) || "알 수 없는 실패";
}

const SERIES_NOTES: Record<string, string> = {
  future_roll: "선물 근월물 연속 — 만기 교체로 끊김이 있을 수 있음",
  market_fx: "ECOS 매매기준율 — 카드의 시장 환율과 다른 계열",
};

function tone(direction: string | null | undefined): string {
  if (direction === "up") return "text-red-700";
  if (direction === "down") return "text-blue-700";
  return "text-gray-500";
}

export function IndicatorHeader({ card, series, name, onRetry }: {
  card: DashboardIndicator | null;
  series: IndicatorSeriesResponse | null;
  name: string;
  onRetry: () => void;
}) {
  const quote = card?.quote ?? null;
  const history = series?.history ?? null;
  const notes = series?.indicator.notes ?? card?.notes ?? [];
  const unit = series?.indicator.unit ?? card?.unit ?? "";
  return (
    <header className="space-y-2">
      <h2 className="text-2xl font-bold tracking-tight">{name}</h2>
      <p className="text-sm text-gray-500">{unit}</p>
      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span data-testid="header-value" className="text-2xl font-semibold tabular-nums">
          {quote ? formatRate(quote.value) : "—"}
        </span>
        {quote && quote.change !== null && (
          <span className={`text-sm tabular-nums ${tone(quote.direction)}`}>
            {quote.direction === "up" ? "▲ " : quote.direction === "down" ? "▼ " : ""}
            {formatRate(quote.change.replace(/^-/, ""))}
            {quote.changeRate !== null && <span className="ml-2">{formatPercent(quote.changeRate)}</span>}
          </span>
        )}
        {quote && card && <span className="text-xs text-gray-500">{stateText(quote, card.market.timezone)}</span>}
        {quote && <span className="text-xs text-gray-500">{previousText(quote)}</span>}
      </div>
      {card && card.notes.includes("market_fx") && (
        <p className="text-xs text-gray-500">카드: {NOTE_TEXT.market_fx}</p>
      )}
      {history && (
        <p className="text-xs text-gray-500">
          저장된 기간 {history.firstDate ?? "—"} ~ {history.lastDate ?? "—"} · 출처 {history.source === "ecos" ? "한국은행 ECOS" : "Yahoo Finance"}
          {history.lastSuccessAt && <> · 마지막 수집 {formatZonedTime(history.lastSuccessAt, KST_ZONE)}</>}
        </p>
      )}
      {notes.map((note) => SERIES_NOTES[note] && (
        <p key={note} className="text-xs text-gray-600">{SERIES_NOTES[note]}</p>
      ))}
      {history?.tailPending && <p className="text-xs text-amber-800">최근 구간 받는 중</p>}
      {history?.lastFailure && (
        <p className="text-xs text-amber-800">
          최근 이어 받기 실패 — {failureLabel(history.lastFailure.kind)} · {formatZonedTime(history.lastFailure.at, KST_ZONE)}
          <button type="button" onClick={onRetry} className="ml-2 text-gray-700 underline">다시 시도</button>
        </p>
      )}
    </header>
  );
}
