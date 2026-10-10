/**
 * 대시보드 화면은 값을 계산하지 않는다 (014 T030) — FR-004, 헌법 원칙 VI.
 *
 * 값·차이·등락률은 서버가 `Decimal`로 낸 문자열이다. 화면이 숫자로 바꿔 계산하면 끝자리가 틀어지고 서버의 값과 다르다
 * (FR-004 실패 양상). 013 `compareNoClientFinance`와 같은 꼴로 대시보드 파일의 숫자 변환을 막는다.
 * 그래프 부품(`IndicatorChart.tsx`)만 그리기 전용 변환을 허용하고, 사유 주석을 요구한다(plan Complexity Tracking).
 */
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "../src");
const FILES = [
  ...readdirSync(join(SRC, "components/dashboard")).map((f) => join(SRC, "components/dashboard", f)),
  join(SRC, "stores/marketQuotesStore.ts"),
  join(SRC, "stores/indicatorSeriesStore.ts"),
  // 014 승인 2026-10-10(반복 2026-10-10b T111) — 지표 모달의 표·까닭 스토어도 값을 계산하지 않는다
  join(SRC, "stores/indicatorTableStore.ts"),
  join(SRC, "stores/indicatorCommentaryStore.ts"),
  join(SRC, "stores/newsStore.ts"),
  join(SRC, "lib/dashboardApi.ts"),
].filter((f) => existsSync(f));

const BANNED = /\b(Number|parseFloat|parseInt)\(/;

describe("대시보드 파일", () => {
  it("검사할 파일이 있다", () => {
    expect(FILES.length).toBeGreaterThan(0);
  });

  it.each(FILES)("%s 에 숫자 변환이 없다", (file) => {
    const body = readFileSync(file, "utf-8");
    if (file.endsWith("IndicatorChart.tsx")) {
      if (BANNED.test(body)) expect(body).toMatch(/그리기 전용/);
      return;
    }
    expect(body).not.toMatch(BANNED);
  });
});
