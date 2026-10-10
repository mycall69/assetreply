/**
 * 외환 일자별 CSV의 등락 두 열 (014 반복 2026-10-10d T143) — FR-031, contracts D10, research R14-24.
 *
 * 두 열은 **맨 끝**이다(004의 진행 중 뒤) — 기존 열의 차례가 그대로라 전에 받은 파일을 읽던 도구가
 * 열을 잘못 읽지 않는다. 값은 서버 글자 그대로(기호·`%` 없음), 없으면 빈 칸이다.
 */
import { describe, expect, it } from "vitest";
import { buildDailyCsv } from "@/lib/csv";
import type { DailyChange, DailyResponse, PeriodRow } from "@/lib/types";

const DERIVED = { cashBuy: "1356.64", cashSell: "1351.76", remitSend: "1354.88", remitReceive: "1353.52" };

const row = (date: string, change: DailyChange | null | undefined): PeriodRow => ({
  date, baseRate: "1425.300000", isProvisional: false, derived: DERIVED,
  periodFrom: date, periodTo: date, isOngoing: false,
  ...(change === undefined ? {} : { change }),
});

const DATA: DailyResponse = {
  currency: "USD", period: "daily", quoteUnit: 1, spreadBasis: "current",
  appliedSpread: { cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" },
  rows: [
    row("2026-10-08", { comparedTo: "2026-10-07", absolute: "2.300000", percent: "0.16", direction: "up" }),
    row("2026-10-07", { comparedTo: "2026-10-06", absolute: "-1.100000", percent: "-0.08", direction: "down" }),
    row("2026-10-06", { comparedTo: "2026-10-05", absolute: "1.000000", percent: null, direction: "up" }),
    row("2026-10-05", null),
    row("2026-10-02", undefined),
  ],
  hasMore: false, oldestReturned: "2026-10-02",
};

const lineOf = (date: string) => buildDailyCsv(DATA).split("\n").find((l) => l.startsWith(date));

describe("일자별 CSV의 등락 두 열", () => {
  it("두 열이 머리 맨 끝(진행 중 뒤)에 있고 앞 열은 그대로다", () => {
    expect(buildDailyCsv(DATA).split("\n")).toContain(
      "날짜,매매기준율,현금 살 때,현금 팔 때,송금 보낼 때,송금 받을 때,확정 여부,원래 기준일,진행 중,등락폭,등락율",
    );
  });

  it("값은 서버 글자 그대로다", () => {
    expect(lineOf("2026-10-08")).toBe(
      "2026-10-08,1425.300000,1356.64,1351.76,1354.88,1353.52,확정,,아니오,2.300000,0.16");
    expect(lineOf("2026-10-07")).toMatch(/,아니오,-1\.100000,-0\.08$/);
  });

  it("비율만 없으면 등락율 칸만 비운다", () => {
    expect(lineOf("2026-10-06")).toMatch(/,아니오,1\.000000,$/);
  });

  it("change가 없거나 null이면 두 칸을 비운다", () => {
    expect(lineOf("2026-10-05")).toMatch(/,아니오,,$/);
    expect(lineOf("2026-10-02")).toMatch(/,아니오,,$/);
  });
});
