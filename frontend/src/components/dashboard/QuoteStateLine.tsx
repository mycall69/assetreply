/**
 * 카드의 장 상태·기준 시각·전일 줄 (014 T039) — FR-004~FR-007, FR-018, contracts D2.
 *
 * 기준 시각은 그 시장의 현지 시각과 한국 시각을 함께 보인다 — 두 시각이 같으면(한국·도쿄) 한 번만. 휴장·개장 전·지난 거래일
 * 마감은 날짜만 보인다. 잠정은 ⏳로 밝힌다(원칙 V) — 장중·점심 휴장은 "잠정", 현지 날짜가 지나지 않은 오늘 마감은 "확정 전"이다.
 */
import { KST_ZONE, formatZonedTime, shortDate } from "@/lib/kstClock";
import type { DashboardIndicator, DashboardQuote } from "@/lib/types";

const STATE_LABELS: Record<DashboardQuote["state"], string> = {
  pre_open: "개장 전",
  open: "장중",
  break: "점심 휴장",
  closed: "마감",
  holiday: "휴장",
};

function times(quote: DashboardQuote, timeZone: string): string {
  const local = formatZonedTime(quote.valueTime, timeZone);
  const kst = formatZonedTime(quote.valueTime, KST_ZONE);
  return local === kst ? local : `${local} (한국 ${kst})`;
}

/** 장 상태 줄 글자. */
export function stateText(quote: DashboardQuote, timeZone: string): string {
  const label = STATE_LABELS[quote.state];
  const day = `${shortDate(quote.sessionDate)} 종가`;
  if (quote.state === "open") {
    const delay = quote.delayMinutes !== null ? ` · 약 ${quote.delayMinutes}분 지연` : "";
    return `${label} ⏳ 잠정 · ${times(quote, timeZone)}${delay}`;
  }
  if (quote.state === "break") return `${label} ⏳ 잠정 · ${times(quote, timeZone)}`;
  if (quote.state === "closed" && quote.provisional) return `${label} ⏳ 확정 전 · ${times(quote, timeZone)}`;
  return `${label} · ${day}`;
}

/** 전일 줄 글자 — 전일 값의 출처를 밝힌다(FR-005·FR-018). */
export function previousText(quote: DashboardQuote): string | null {
  const previous = quote.previous;
  if (!previous) return "전일 값을 알 수 없습니다";
  if (previous.from === "source_fx") return "전일: 런던 0시 기준(출처)";
  if (previous.from === "source") return "전일 값: 출처(이력에 아직 없음)";
  return previous.date ? `전일 ${shortDate(previous.date)}` : null;
}

export const NOTE_TEXT: Record<DashboardIndicator["notes"][number], string> = {
  market_fx: "시장 환율 — 매매기준율과 다를 수 있음",
  future_roll: "선물 근월물 연속",
};

export function QuoteStateLine({ indicator, quote }: { indicator: DashboardIndicator; quote: DashboardQuote }) {
  const previous = previousText(quote);
  return (
    <div className="mt-2 space-y-0.5 text-xs text-gray-500">
      <p data-testid="card-state">{stateText(quote, indicator.market.timezone)}</p>
      {previous && <p data-testid="card-previous">{previous}</p>}
      {indicator.notes.map((note) => <p key={note}>{NOTE_TEXT[note]}</p>)}
    </div>
  );
}
