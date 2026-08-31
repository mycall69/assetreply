/**
 * CSV 조립 테스트 (T071, T072) — FR-044~047, research R2-7.
 *
 * **정밀도가 핵심이다.** 서버가 준 문자열을 그대로 담아야 하며, `Number()`가 한 번이라도
 *끼면 헌법 원칙 VI가 파일 출력 단계에서 무너진다.
 */
import { describe, expect, it } from "vitest";
import { buildDailyCsv } from "@/lib/csv";
import type { DailyResponse } from "@/lib/types";

const SPREAD = {
  cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500",
};

const DATA: DailyResponse = {
  currency: "USD", quoteUnit: 1, appliedSpread: SPREAD, spreadBasis: "current",
  rows: [
    { date: "2026-08-30", baseRate: "1354.200000", isProvisional: true,
      derived: { cashBuy: "1356.64", cashSell: "1351.76", remitSend: "1354.88", remitReceive: "1353.52" } },
    { date: "2026-08-29", baseRate: "1356.100000", isProvisional: false,
      derived: { cashBuy: "1358.54", cashSell: "1353.66", remitSend: "1356.78", remitReceive: "1355.42" } },
  ],
  hasMore: false, oldestReturned: "2026-08-29",
};

describe("일자별 상세 CSV", () => {
  it("저장 정밀도를 그대로 담는다", () => {
    const csv = buildDailyCsv(DATA);
    expect(csv).toContain("1354.200000");
    expect(csv).not.toContain("1354.2,");
  });

  it("잠정 행을 구분할 수 있다", () => {
    const lines = buildDailyCsv(DATA).split("\n");
    const provisional = lines.find((l) => l.startsWith("2026-08-30"));
    const confirmed = lines.find((l) => l.startsWith("2026-08-29"));
    expect(provisional).toContain("잠정");
    expect(confirmed).toContain("확정");
  });

  it("통화·구간·적용 스프레드를 머리말에 담는다", () => {
    const csv = buildDailyCsv(DATA);
    expect(csv).toContain("USD");
    expect(csv).toContain("2026-08-29");
    expect(csv).toContain("0.001800");
    expect(csv).toContain("현재 스프레드를 각 날짜에 적용한 가정");
  });

  it("열 머리글을 담는다", () => {
    expect(buildDailyCsv(DATA)).toContain(
      "날짜,매매기준율,현금 살 때,현금 팔 때,송금 보낼 때,송금 받을 때,확정 여부",
    );
  });

  it("쉼표를 포함한 값은 따옴표로 감싼다", () => {
    const csv = buildDailyCsv({
      ...DATA,
      rows: [{ ...DATA.rows[0], baseRate: "1,354.20" }],
    });
    expect(csv).toContain('"1,354.20"');
  });

  it("따옴표를 포함한 값은 이스케이프한다", () => {
    const csv = buildDailyCsv({
      ...DATA,
      rows: [{ ...DATA.rows[0], baseRate: 'a"b' }],
    });
    expect(csv).toContain('"a""b"');
  });

  it("행이 없어도 머리글은 남는다", () => {
    const csv = buildDailyCsv({ ...DATA, rows: [] });
    expect(csv).toContain("날짜,매매기준율");
  });
});
