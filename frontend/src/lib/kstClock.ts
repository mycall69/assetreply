/**
 * 한국 시간 날짜·시장 현지 시각 (014 T037) — FR-002, FR-004, research R14-15.
 *
 * 오늘 날짜는 **브라우저의 시간대와 무관하게 한국 시간**이다 — 다른 시간대에서 열면 날짜가 어긋나지 않게 한다. 시장의 기준 시각은
 * 그 시장의 현지 시각(IANA 시간대 — 서머타임 포함)이다. 모두 `Intl.DateTimeFormat`의 시간대 변환이다(시차를 고정하지 않는다).
 */

const KST = "Asia/Seoul";
const DAY_MS = 24 * 60 * 60 * 1000;

function parts(date: Date, timeZone: string): Record<string, string> {
  const out: Record<string, string> = {};
  const format = new Intl.DateTimeFormat("en-US", {
    timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
    second: "2-digit", hourCycle: "h23",
  });
  for (const p of format.formatToParts(date)) out[p.type] = p.value;
  return out;
}

/** "2026년 10월 9일 (금)" — 한국 날짜와 요일. */
export function formatKstDate(now: Date): string {
  const weekday = new Intl.DateTimeFormat("ko-KR", { timeZone: KST, weekday: "short" }).format(now);
  const p = parts(now, KST);
  return `${p.year}년 ${p.month.replace(/^0/, "")}월 ${p.day.replace(/^0/, "")}일 (${weekday})`;
}

/** 다음 한국 자정까지의 밀리초 — 화면의 날짜를 바꿀 타이머(FR-002). */
export function msUntilNextKstMidnight(now: Date): number {
  const p = parts(now, KST);
  const elapsed = ((Number.parseInt(p.hour, 10) * 60 + Number.parseInt(p.minute, 10)) * 60
    + Number.parseInt(p.second, 10)) * 1000 + now.getMilliseconds();
  return DAY_MS - elapsed;
}

function parse(iso: string): Date | null {
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** 그 시간대의 "HH:mm". 읽을 수 없으면 글자 그대로. */
export function formatZonedTime(iso: string, timeZone: string): string {
  const date = parse(iso);
  if (!date) return iso;
  const p = parts(date, timeZone);
  return `${p.hour}:${p.minute}`;
}

/** 그 시간대의 "MM-DD". 읽을 수 없으면 글자 그대로. */
export function formatZonedDate(iso: string, timeZone: string): string {
  const date = parse(iso);
  if (!date) return iso;
  const p = parts(date, timeZone);
  return `${p.month}-${p.day}`;
}

/** 그 시간대의 "YYYY-MM-DD" — 두 시각이 같은 날인지 견준다. 읽을 수 없으면 글자 그대로. */
export function formatZonedDay(iso: string, timeZone: string): string {
  const date = parse(iso);
  if (!date) return iso;
  const p = parts(date, timeZone);
  return `${p.year}-${p.month}-${p.day}`;
}

/** 거래일 "YYYY-MM-DD" → "MM-DD". */
export function shortDate(day: string): string {
  return day.length >= 10 ? day.slice(5, 10) : day;
}

export const KST_ZONE = KST;
