/**
 * 원금 쉼표 (T111) — 006 FR-053, SC-018, research R6-20, ui-wireframes W3. 반복 2026-10-03.
 *
 * **쉼표는 표시에만 있다.** 요청·이력에는 쉼표 없는 문자열이 간다 — 서버는 원금을 `Decimal`로 읽어
 * 쉼표가 섞이면 400을 낸다(헌법 원칙 VI, 원금은 문자열 그대로).
 */
import { describe, expect, it } from "vitest";
import { caretAfter, formatPrincipal, normalizePrincipal } from "@/lib/principalFormat";

describe("표시 형식", () => {
  it.each([
    ["10000000", "10,000,000"],
    ["1000", "1,000"],
    ["999", "999"],
    ["0", "0"],
    ["1234.5", "1,234.5"],
    ["1234.567", "1,234.567"],
    ["1000.", "1,000."],
    ["", ""],
  ])("%s → %s", (raw, shown) => {
    expect(formatPrincipal(raw)).toBe(shown);
  });

  it("소수부는 묶지도 반올림하지도 않는다", () => {
    expect(formatPrincipal("1000.123456")).toBe("1,000.123456");
  });
});

describe("쉼표 없는 값", () => {
  it.each([
    ["10,000,000", "10000000"],
    ["1,234.5", "1234.5"],
    [" 1 000 원", "1000"],
    ["12a3", "123"],
    ["1.2.3", "1.23"],
    ["", ""],
  ])("%j → %j", (typed, raw) => {
    expect(normalizePrincipal(typed)).toBe(raw);
  });

  it("표시 형식을 다시 읽으면 원래 값이다", () => {
    for (const raw of ["10000000", "1234.5", "7", "1000."]) {
      expect(normalizePrincipal(formatPrincipal(raw))).toBe(raw);
    }
  });
});

describe("커서 위치", () => {
  // 쉼표가 끼어들면 글자 수가 바뀌어 커서가 끝으로 튄다. 커서 앞의 숫자 개수로 되돌린다.
  it.each([
    ["10,000,000", 0, 0],
    ["10,000,000", 2, 2],
    ["10,000,000", 3, 4],
    ["10,000,000", 8, 10],
    ["1,234.5", 5, 6],
  ])("%s에서 숫자 %i개 뒤 → %i", (shown, digits, caret) => {
    expect(caretAfter(shown, digits)).toBe(caret);
  });
});
