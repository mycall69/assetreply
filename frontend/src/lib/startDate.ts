/**
 * 시작일 산술 (T060) — 006 FR-001~004, research R6-7.
 *
 * **`Date` 객체로 더하지 않는다.** `setMonth(+1)`은 1월 31일을 3월 2일(또는 3일)로 넘긴다 —
 * FR-003이 막으려는 바로 그 동작이다. 사용자가 고른 달이 바뀌는데 표의 첫 행만 엉뚱한 달에서
 * 시작하고 오류는 없다. 문자열 `YYYY-MM-DD`를 정수로 나눠 계산하고, 없는 날은 **그 달의 마지막
 * 날**로 맞춘다. 문자열을 `Date`로 바꾸는 순간 시간대가 끼어 하루가 밀리는 경로도 생긴다.
 */

/** 처음 들어오면 시작일 (FR-001). */
export const DEFAULT_START = "2020-01-01";

interface Ymd {
  y: number;
  m: number;
  d: number;
}

const PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

function isLeap(y: number): boolean {
  return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
}

function daysInMonth(y: number, m: number): number {
  if (m === 2) return isLeap(y) ? 29 : 28;
  return [4, 6, 9, 11].includes(m) ? 30 : 31;
}

function parse(text: string): Ymd | null {
  const match = PATTERN.exec(text);
  if (match === null) return null;
  const [y, m, d] = [match[1], match[2], match[3]].map((p) => Number.parseInt(p, 10));
  if (m < 1 || m > 12 || d < 1 || d > daysInMonth(y, m)) return null;
  return { y, m, d };
}

const pad = (n: number, width = 2) => String(n).padStart(width, "0");

function format({ y, m, d }: Ymd): string {
  return `${pad(y, 4)}-${pad(m)}-${pad(d)}`;
}

/** 직접 입력한 값이 있는 날짜인가. */
export function isValidDate(text: string): boolean {
  return parse(text) !== null;
}

/** `YYYY-MM`. "그 달로 옮기기"의 이름에 쓴다. */
export function monthOf(date: string): string {
  return date.slice(0, 7);
}

function target(date: Ymd, months: number): Ymd {
  const index = date.y * 12 + (date.m - 1) + months;
  const y = Math.floor(index / 12);
  const m = (index % 12) + 1;
  return { y, m, d: Math.min(date.d, daysInMonth(y, m)) };
}

/**
 * `months`개월 옮긴다(1년은 12개월). 없는 날은 그 달의 마지막 날로 맞추고(FR-003), 어제보다 뒤가
 * 되면 어제에서 멈춘다(FR-004). 맞춰진 날짜에서 다시 옮기면 **맞춰진 날짜에서** 출발한다 —
 * 원래 날을 기억하지 않는다.
 */
export function shift(date: string, months: number, limit: string): string {
  const parsed = parse(date);
  if (parsed === null) return date;
  const moved = format(target(parsed, months));
  return moved > limit ? limit : moved;
}

/** 그 이동이 가능한가. **어제가 속한 달을 넘어가는 이동**은 할 수 없다(W1). */
export function canShift(date: string, months: number, limit: string): boolean {
  const parsed = parse(date);
  const bound = parse(limit);
  if (parsed === null || bound === null) return false;
  const moved = target(parsed, months);
  return moved.y * 12 + moved.m <= bound.y * 12 + bound.m;
}

/** 그 날의 어제. */
export function yesterdayOf(today: string): string {
  const parsed = parse(today);
  if (parsed === null) return today;
  if (parsed.d > 1) return format({ ...parsed, d: parsed.d - 1 });
  const prev = target({ ...parsed, d: 1 }, -1);
  return format({ ...prev, d: daysInMonth(prev.y, prev.m) });
}

/**
 * 브라우저의 지역 날짜로 본 어제. 사용자가 한국에 있다는 001~005의 전제이고, 서버도 계산 끝을
 * 어제로 잡으므로 기준이 같다(research R6-7). 오늘을 읽을 때만 `Date`를 쓴다 — 더하지 않는다.
 */
export function localYesterday(now: Date = new Date()): string {
  return yesterdayOf(format({ y: now.getFullYear(), m: now.getMonth() + 1, d: now.getDate() }));
}

/**
 * UTC로 본 어제 — 마지막으로 마감된 UTC 하루 (007 FR-009, FR-022). 가상자산의 일봉은 UTC 00:00 기준이다(헌법 원칙 V). 한국 시간
 * 어제로 두면 한국 오전 9시 전에는 아직 마감되지 않은 UTC 하루를 고를 수 있다 — 서버는 그 일봉을 저장하지 않는다.
 */
export function utcYesterday(now: Date = new Date()): string {
  return yesterdayOf(format({
    y: now.getUTCFullYear(), m: now.getUTCMonth() + 1, d: now.getUTCDate() }));
}

/**
 * 한국 시간으로 본 오늘 (008 FR-005, FR-018). 예금은 매일 이자가 붙어(경과분) 계산 끝이 **오늘**이다 — 서버도 한국 시간
 * 오늘로 잡는다. 브라우저의 시간대에 기대지 않는다 — 다른 시간대에서 열면 하루가 어긋난다. 오늘을 읽을 때만 `Date`를 쓴다.
 */
export function kstToday(now: Date = new Date()): string {
  const kst = new Date(now.getTime() + 9 * 60 * 60 * 1000);
  return format({ y: kst.getUTCFullYear(), m: kst.getUTCMonth() + 1, d: kst.getUTCDate() });
}
