/**
 * 시작일 산술 (T056) — 006 FR-002, FR-003, FR-004, SC-012, research R6-7.
 *
 * **`Date`의 `setMonth(+1)`은 1월 31일을 3월 2일(또는 3일)로 넘긴다** — FR-003이 막으려는 바로 그
 * 동작이다. 사용자가 고른 달이 바뀌는데 표의 첫 행만 엉뚱한 달에서 시작하고 오류는 없다. 그래서
 * 문자열을 정수로 나눠 계산한다.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  DEFAULT_START,
  canShift,
  isValidDate,
  shift,
  yesterdayOf,
} from "@/lib/startDate";

const LIMIT = "2026-10-01";

describe("기본값", () => {
  it("2020-01-01이다", () => {
    expect(DEFAULT_START).toBe("2020-01-01");
  });
});

describe("이동 (FR-003 — 없는 날은 그 달의 마지막 날로)", () => {
  it.each([
    ["2020-01-31", 1, "2020-02-29"],     // 윤년 2월
    ["2021-01-31", 1, "2021-02-28"],
    ["2020-03-31", -1, "2020-02-29"],
    ["2020-02-29", 12, "2021-02-28"],    // 1년 뒤
    ["2020-02-29", -12, "2019-02-28"],
    ["2016-02-29", 48, "2020-02-29"],    // 4년 뒤 윤년 (어제 경계 안)
    ["2020-05-31", 1, "2020-06-30"],
    ["2020-12-15", 1, "2021-01-15"],     // 해 넘김
    ["2021-01-15", -1, "2020-12-15"],
    ["2020-01-01", -12, "2019-01-01"],
  ])("%s에서 %s개월 → %s", (from, months, expected) => {
    expect(shift(from, months, LIMIT)).toBe(expected);
  });

  it("맞춰진 날짜에서 다시 이동하면 맞춰진 날짜에서 출발한다", () => {
    // 1월 31일 → 2월 29일 → 3월 29일. 원래의 31일을 기억해 3월 31일로 가지 않는다.
    const feb = shift("2020-01-31", 1, LIMIT);
    expect(shift(feb, 1, LIMIT)).toBe("2020-03-29");
  });
});

describe("어제 경계 (FR-004)", () => {
  it("어제보다 뒤로는 옮겨지지 않는다 — 어제로 멈춘다", () => {
    expect(shift("2026-09-15", 1, LIMIT)).toBe(LIMIT);
    expect(shift("2026-09-01", 1, LIMIT)).toBe(LIMIT);
  });

  it("어제가 속한 달을 넘어가는 이동은 할 수 없다", () => {
    expect(canShift("2026-09-15", 1, LIMIT)).toBe(true);    // 10월로 — 어제의 달
    expect(canShift("2026-10-01", 1, LIMIT)).toBe(false);   // 11월로
    expect(canShift("2025-11-15", 12, LIMIT)).toBe(false);  // 2026-11로
    expect(canShift("2025-10-15", 12, LIMIT)).toBe(true);
    expect(canShift("2026-10-01", -1, LIMIT)).toBe(true);
  });

  it.each([
    ["2026-10-02", "2026-10-01"],
    ["2026-03-01", "2026-02-28"],
    ["2024-03-01", "2024-02-29"],
    ["2026-01-01", "2025-12-31"],
  ])("%s의 어제는 %s", (today, expected) => {
    expect(yesterdayOf(today)).toBe(expected);
  });
});

describe("직접 입력", () => {
  it.each([
    ["2020-02-29", true],
    ["2021-02-29", false],
    ["2020-13-01", false],
    ["2020-1-1", false],
    ["", false],
    ["abcd-ef-gh", false],
  ])("%s → %s", (text, valid) => {
    expect(isValidDate(text)).toBe(valid);
  });
});

describe("정적 검사", () => {
  it("startDate.ts가 Date의 월·년 덧셈을 쓰지 않는다", () => {
    const src = readFileSync(join(process.cwd(), "src", "lib", "startDate.ts"), "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    expect(src).not.toMatch(/setMonth|setFullYear|setDate/);
  });
});
