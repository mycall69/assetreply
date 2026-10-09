/**
 * 한국 시간 날짜·시각 (014 T024) — FR-002, FR-004, research R14-15.
 *
 * 오늘 날짜는 **브라우저의 시간대와 무관하게 한국 시간**이다. 기준 시각은 그 시장의 현지 시각과 한국 시각이다.
 * 자정 타이머는 다음 한국 자정까지의 시간이다 — 화면을 연 순간의 날짜를 고정하면 밤새 열어 둔 화면이 어제 날짜를 보인다.
 */
import { describe, expect, it } from "vitest";
import {
  formatKstDate,
  formatZonedDate,
  formatZonedTime,
  msUntilNextKstMidnight,
} from "@/lib/kstClock";

describe("한국 날짜", () => {
  it("요일과 함께 한국 날짜다", () => {
    // 2026-10-09 05:30 UTC = 한국 14:30(금) = 뉴욕 01:30(금)
    expect(formatKstDate(new Date("2026-10-09T05:30:00Z"))).toBe("2026년 10월 9일 (금)");
  });

  it("UTC로는 전날이어도 한국 날짜다", () => {
    // 2026-10-09 16:00 UTC = 한국 10-10 01:00(토)
    expect(formatKstDate(new Date("2026-10-09T16:00:00Z"))).toBe("2026년 10월 10일 (토)");
  });
});

describe("다음 한국 자정", () => {
  it("23:59:30에서 30초", () => {
    expect(msUntilNextKstMidnight(new Date("2026-10-09T14:59:30Z"))).toBe(30_000);
  });

  it("자정 바로 뒤는 거의 하루", () => {
    expect(msUntilNextKstMidnight(new Date("2026-10-09T15:00:00Z"))).toBe(24 * 60 * 60 * 1000);
  });
});

describe("시장 현지 시각", () => {
  it("뉴욕·한국 시각", () => {
    expect(formatZonedTime("2026-10-08T20:00:00Z", "America/New_York")).toBe("16:00");
    expect(formatZonedTime("2026-10-08T20:00:00Z", "Asia/Seoul")).toBe("05:00");
  });

  it("현지 날짜(월-일)", () => {
    expect(formatZonedDate("2026-10-08T23:30:00Z", "America/New_York")).toBe("10-08");
    expect(formatZonedDate("2026-10-08T23:30:00Z", "Asia/Seoul")).toBe("10-09");
  });

  it("읽을 수 없는 시각은 글자 그대로", () => {
    expect(formatZonedTime("not-a-date", "Asia/Seoul")).toBe("not-a-date");
  });
});
