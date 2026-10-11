/**
 * 기준금리 화면의 날짜 글자·기간 (014 반복 2026-10-11d T209) — FR-040, FR-041, contracts D18.
 *
 * 금리·전회대비는 서버 글자 그대로다(원칙 VI — 여기서 계산하지 않는다). 여기는 날짜 글자와 기간의 처음 보이는 범위만 다룬다 — 결정일은
 * 한국 날짜(`YYYY-MM-DD`) 글자라 글자로 견준다(시간대 변환이 없다).
 */
import { formatZonedDay, KST_ZONE } from "@/lib/kstClock";
import { RATE_RANGES, type RateRange } from "@/lib/types";

/** "2026-10-22" → "2026. 10. 22." (스크린샷과 같은 꼴). */
export function dottedDate(day: string): string {
  const [year, month, date] = day.split("-");
  return year && month && date ? `${year}. ${month}. ${date}.` : day;
}

/** 칸의 기준 일자 — 올해(한국)면 "09. 17.", 아니면 "25. 12. 18.". */
export function shortDottedDate(day: string, thisYear: string): string {
  const [year, month, date] = day.split("-");
  if (!year || !month || !date) return day;
  return year === thisYear ? `${month}. ${date}.` : `${year.slice(2)}. ${month}. ${date}.`;
}

/** 지금 한국 날짜의 연도 글자. */
export function kstYear(now: Date = new Date()): string {
  return formatZonedDay(now.toISOString(), KST_ZONE).slice(0, 4);
}

/** 그 날짜에서 거꾸로 `years`년 — 글자로(2월 29일은 그대로 두어도 글자 견주기에 맞다). */
export function yearsBefore(day: string, years: number): string {
  const year = Number(day.slice(0, 4));
  if (!Number.isInteger(year)) return day;
  return `${String(year - years).padStart(4, "0")}${day.slice(4)}`;
}

const YEARS: Record<Exclude<RateRange, "all">, number> = { "1y": 1, "5y": 5, "10y": 10 };

/** 금리 모달 기간의 처음 보이는 범위 시작 — 마지막 결정에서 거꾸로 센다. "모두"·결정 없음은 `null`(전체). */
export function rateWindowStart(range: RateRange, lastDecidedOn: string | null): string | null {
  if (range === "all" || lastDecidedOn === null) return null;
  return yearsBefore(lastDecidedOn, YEARS[range]);
}

/** 주소의 기간 → 금리 기간. 금리에 없는 기간(일·주·월·20년)은 처음 기간(1년)이다. */
export function rateRangeOf(raw: string | null | undefined): RateRange {
  return RATE_RANGES.find((r) => r === raw) ?? "1y";
}
