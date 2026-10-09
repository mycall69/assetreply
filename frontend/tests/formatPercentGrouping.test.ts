/**
 * 백분율 천 단위 쉼표 (013 반복 2026-10-09c T108) — FR-021, SC-012, research R13-20.
 *
 * 공유 형식 함수 `formatPercent`가 정수부를 세 자리마다 쉼표로 끊는다 — 비교 화면과 네 메뉴 화면이 같은 글자다. 1,000% 미만·부호·소수 자리·자르기(반올림하지
 * 않음)는 그대로다. 쉼표는 문자열로만 넣는다(원칙 VI).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { formatPercent } from "@/lib/format";

describe("천 단위 쉼표", () => {
  it.each([
    ["17.6191", "+1,761.91%"],
    ["20.455734", "+2,045.57%"],
    ["-12.345", "-1,234.50%"],
    ["123456.789", "+12,345,678.90%"],
    ["10", "+1,000.00%"],
  ])("%s → %s", (value, text) => {
    expect(formatPercent(value)).toBe(text);
  });

  it.each([
    ["9.9999", "+999.99%"],
    ["0.358", "+35.80%"],
    ["-0.005", "-0.50%"],
    ["0", "+0.00%"],
  ])("1,000%% 미만은 그대로 — %s → %s", (value, text) => {
    expect(formatPercent(value)).toBe(text);
  });

  it("소수 자리 인자와 자르기(반올림하지 않음)는 그대로다", () => {
    expect(formatPercent("15.192831")).toBe("+1,519.28%");
    expect(formatPercent("15.192831", 0)).toBe("+1,519%");
    expect(formatPercent("15.192831", 4)).toBe("+1,519.2831%");
  });

  it("lib/format.ts의 숫자 변환이 늘지 않는다(문자열로만 끊는다)", () => {
    const source = readFileSync(join(process.cwd(), "src/lib/format.ts"), "utf-8")
      .replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    // 축 눈금 전용(`formatAxisNumber`)의 `Number(fixed)` 한 곳뿐이다.
    expect(source.match(/\b(Number|parseFloat|parseInt)\s*\(/g) ?? []).toEqual(["Number("]);
  });
});
