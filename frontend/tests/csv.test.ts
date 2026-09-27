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
  currency: "USD", period: "daily", quoteUnit: 1, appliedSpread: SPREAD, spreadBasis: "current",
  rows: [
    { date: "2026-08-30", baseRate: "1354.200000", isProvisional: true,
      periodFrom: "2026-08-30", periodTo: "2026-08-30", isOngoing: false,
      derived: { cashBuy: "1356.64", cashSell: "1351.76", remitSend: "1354.88", remitReceive: "1353.52" } },
    { date: "2026-08-29", baseRate: "1356.100000", isProvisional: false,
      periodFrom: "2026-08-29", periodTo: "2026-08-29", isOngoing: false,
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

/**
 * 004 T033 — FR-016a, FR-016b, FR-016c, SC-018, SC-019, SC-020.
 *
 * **표시가 파일에서 빠지면 화면에서 막은 오해가 파일에서 되살아난다.** 파일만 본
 * 사람은 2026-08-14를 그냥 8월 데이터로 읽지, 8월 31일의 대체값인 줄 모른다.
 */
const WEEKLY: DailyResponse = {
  ...DATA, period: "weekly",
  rows: [
    { date: "2026-07-16", baseRate: "1401.200000", isProvisional: false,
      periodFrom: "2026-07-13", periodTo: "2026-07-19",
      shiftedFrom: "2026-07-17", isOngoing: false,
      derived: { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" } },
    { date: "2026-07-24", baseRate: "1383.800000", isProvisional: false,
      periodFrom: "2026-07-20", periodTo: "2026-07-26", isOngoing: true,
      derived: { cashBuy: "1", cashSell: "1", remitSend: "1", remitReceive: "1" } },
  ],
  hasMore: true, oldestReturned: "2026-07-24",
};

describe("기간 단위 내려받기", () => {
  it("파일의 기간 단위가 화면과 같다", () => {
    // FR-016a, SC-018 — 화면에서 30행을 보다가 17,000행 파일을 받으면 사용자는
    // 무엇을 받았는지 확인하려고 파일을 열어야 한다.
    expect(buildDailyCsv(WEEKLY)).toContain("# 기간 단위,주별");
    expect(buildDailyCsv(DATA)).toContain("# 기간 단위,일별");
    expect(buildDailyCsv({ ...WEEKLY, period: "monthly" })).toContain("# 기간 단위,월별");
  });

  it("원래 기준일이 열로 남는다", () => {
    // FR-016b, SC-019 — 빠지면 파일만 본 사람은 그 날짜를 금요일 값으로 읽는다.
    const line = buildDailyCsv(WEEKLY).split("\n").find((l) => l.startsWith("2026-07-16"));
    expect(line).toContain("2026-07-17");
  });

  it("옮겨지지 않은 행의 원래 기준일 칸은 비어 있다", () => {
    const line = buildDailyCsv(WEEKLY).split("\n").find((l) => l.startsWith("2026-07-24"));
    expect(line).not.toContain("2026-07-17");
  });

  it("진행 중 여부가 열로 남는다", () => {
    const lines = buildDailyCsv(WEEKLY).split("\n");
    expect(lines.find((l) => l.startsWith("2026-07-24"))).toMatch(/예$/);
    expect(lines.find((l) => l.startsWith("2026-07-16"))).toMatch(/아니오$/);
  });

  it("열 머리글에 두 열이 더해진다", () => {
    expect(buildDailyCsv(WEEKLY)).toContain("확정 여부,원래 기준일,진행 중");
  });

  it("담긴 범위를 머리말에 밝힌다", () => {
    // FR-016c, SC-020 — 범위를 밝히지 않으면 사용자는 표 전체를 받았다고 믿는다.
    // 3페이지를 훑고 90행을 받았는데 그것이 60년치라고 오해한다.
    const csv = buildDailyCsv(WEEKLY);
    expect(csv).toContain("# 담긴 범위,2026-07-24 ~ 2026-07-16 (2행)");
    expect(csv).toContain("화면에 쌓인 행만 담깁니다");
  });
});
