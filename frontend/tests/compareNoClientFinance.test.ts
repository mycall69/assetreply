/**
 * 비교 화면의 클라이언트 계산 금지 정적 검사 (013 T021) — 헌법 원칙 VI, research R13-11.
 *
 * 비교 표의 값·비용 합·몫·주 값은 서버가 낸다. 화면은 견주기만 한다(정렬 — `lib/decimalOrder`). `Number()`·`parseFloat()`가 한 번이라도
 * 끼면 IEEE 754 연산이 되어 큰 원화 금액·긴 소수의 차례가 틀릴 수 있다 — 어겨져도 조용하므로 기계적으로 막는다. 기존 검사
 * (`noClientSideFinance.test.ts`)와 같은 규칙이고, 그 파일 목록은 고치지 않는다.
 *
 * 최종 지표 막대(`CompareMetricBars`)는 막대 **길이만** 그리기 전용으로 숫자를 쓴다 — 이 목록에 넣지 않는다(plan Complexity Tracking).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(process.cwd(), "src");

const COMPARE_MONEY_FILES = [
  "components/compare/CompareTable.tsx",
  "components/compare/CostCell.tsx",
  "lib/decimalOrder.ts",
  "lib/compareBlock.ts",
  "lib/compareCondition.ts",
  "stores/compareStore.ts",
];

const NUMERIC_CAST = /\b(Number|parseFloat|parseInt)\s*\(/;

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
}

describe("비교 화면의 클라이언트 계산 금지", () => {
  it("금액·비율을 다루는 비교 파일에 숫자 변환이 없다", () => {
    const offenders = COMPARE_MONEY_FILES.filter((rel) =>
      NUMERIC_CAST.test(stripComments(readFileSync(join(SRC, rel), "utf-8"))));
    expect(offenders).toEqual([]);
  });
});
