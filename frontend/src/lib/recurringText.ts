/**
 * 적립식 주기 안내 문장 (011 T027) — FR-003, ui-wireframes §1.
 *
 * **날짜를 계산하지 않는다.** 실제 납입일(휴장일 미루기·말일)은 서버가 정한다 — 화면은 시작일 문자열의 요일·날짜 이름만 말한다. 요일은 `Date`를
 * 거치지 않고 정수로 센다(시간대가 끼면 하루가 밀린다 — `startDate.ts`와 같은 이유).
 */

import type { Frequency, InvestmentPlan } from "./types";

const PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const WEEKDAYS = ["일", "월", "화", "수", "목", "금", "토"] as const;

/** 금액 칸의 이름 — 투자 방식을 따른다. */
export function amountLabel(mode: InvestmentPlan["mode"]): string {
  return mode === "recurring" ? "한 번 납입액" : "투자 원금";
}

function daysIn(y: number, m: number): number {
  if (m === 2) return (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0 ? 29 : 28;
  return [4, 6, 9, 11].includes(m) ? 30 : 31;
}

/** 그레고리력 요일(0 = 일요일) — 사카모토 방법. */
function weekday(y: number, m: number, d: number): number {
  const t = [0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4];
  const year = m < 3 ? y - 1 : y;
  return (year + Math.floor(year / 4) - Math.floor(year / 100) + Math.floor(year / 400) + t[m - 1] + d) % 7;
}

/**
 * 주기와 시작일에서 "언제 넣는지" 한 문장. 시작일이 날짜가 아니면 빈 문자열이다.
 *
 * 주식은 휴장이면 다음 거래일, 가상자산은 일봉이 없으면(출처 결측) 다음 날이다(FR-004).
 */
export function frequencyNote(frequency: Frequency, start: string, asset: "stock" | "crypto"): string {
  const match = PATTERN.exec(start);
  if (match === null) return "";
  const [y, m, d] = [match[1], match[2], match[3]].map((p) => Number.parseInt(p, 10));
  if (m < 1 || m > 12 || d < 1 || d > daysIn(y, m)) return "";
  const later = asset === "stock" ? "휴장이면 다음 거래일" : "일봉이 없으면 다음 날";
  switch (frequency) {
    case "daily":
      return asset === "stock" ? "거래일마다 넣습니다." : "날마다(UTC 하루) 넣습니다(일봉이 없으면 다음 날).";
    case "weekly":
      return `매주 ${WEEKDAYS[weekday(y, m, d)]}요일(${later})에 넣습니다.`;
    case "monthly":
      return d >= 29
        ? `매달 ${d}일(없는 달은 말일, ${later})에 넣습니다.`
        : `매달 ${d}일(${later})에 넣습니다.`;
    case "yearly":
      return m === 2 && d === 29
        ? `매년 2월 29일(평년은 2월 28일, ${later})에 넣습니다.`
        : `매년 ${m}월 ${d}일(${later})에 넣습니다.`;
  }
}
