/**
 * 클라이언트 금융 계산 금지 정적 검사 (T075).
 *
 * 헌법 원칙 VI: 금융 계산에 `float` 금지. 브라우저에는 `Decimal`이 없으므로
 * `Number()`·`parseFloat()`가 한 번이라도 끼면 IEEE 754 연산이 되고, 원칙 VI가
 * API 경계와 파일 출력 단계에서 무너진다 (research R2-5·R2-7).
 *
 * 사람이 리뷰로 잡기 어렵고 어겨져도 조용하므로 기계적으로 막는다.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

/** 금액·비율 문자열을 다루는 파일 — 여기서 숫자 변환이 나오면 위반이다. */
const MONEY_FILES = [
  "lib/csv.ts",
  "components/fx/DailyTable.tsx",
  "components/fx/RateSummary.tsx",
];

const NUMERIC_CAST = /\b(Number|parseFloat|parseInt)\s*\(/;

/** 주석·문자열의 언급은 코드가 아니다. 규칙 설명 자체가 걸리면 검사가 무의미해진다. */
function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    return statSync(full).isDirectory() ? walk(full) : [full];
  });
}

describe("클라이언트 금융 계산 금지", () => {
  it("금액을 다루는 파일에 숫자 변환이 없다", () => {
    const offenders = MONEY_FILES.filter((rel) =>
      NUMERIC_CAST.test(stripComments(readFileSync(join(SRC, rel), "utf-8"))),
    );
    expect(offenders).toEqual([]);
  });

  it("파생 환율을 클라이언트에서 계산하지 않는다", () => {
    // 서버가 산출해 문자열로 내려준다 (research R2-5). 곱셈이 나오면 위반이다.
    const offenders = walk(join(SRC, "components", "fx"))
      .filter((f) => /\*\s*\(1\s*[+-]|deriveRates|cashBuy\s*\*/.test(readFileSync(f, "utf-8")))
      .map((f) => f.replace(SRC, ""));
    expect(offenders).toEqual([]);
  });

  it("CSV는 문자열 연결만 한다", () => {
    const csv = readFileSync(join(SRC, "lib", "csv.ts"), "utf-8");
    expect(csv).not.toMatch(/toFixed|Math\./);
  });
});
