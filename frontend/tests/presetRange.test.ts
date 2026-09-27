/**
 * 프리셋 구간 환산 (T091) — 002 FR-015, FR-019.
 *
 * `presetStart`는 "오늘로부터 N년 전"을 날짜로 바꾼다. 축적 시작일보다 이르면 **그 날짜로
 * 자른다** — 없는 구간을 요청해도 서버가 빈 응답을 주지 않도록 하는 것이 FR-019의 절반이다.
 *
 * 시각을 고정한다. 고정하지 않으면 오늘이 언제냐에 따라 기대값이 달라져, 테스트가 통과하는
 * 날과 실패하는 날이 생긴다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { presetStart } from "@/stores/fxWorkspaceStore";
import type { CoverageRow } from "@/lib/types";

const USD: CoverageRow = {
  currency: "USD", coveredFrom: "1964-05-04", coveredThrough: "2026-09-26",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-09-27T00:00:00Z",
};

const EUR: CoverageRow = {
  currency: "EUR", coveredFrom: "1994-01-03", coveredThrough: "2026-09-26",
  firstAvailableDate: "1994-01-03", lastUpdatedAt: "2026-09-27T00:00:00Z",
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-09-27T12:00:00Z")); // 어제 = 2026-09-26
});

afterEach(() => {
  vi.useRealTimers();
});

describe("프리셋 환산", () => {
  it("월 단위 프리셋을 환산한다", () => {
    expect(presetStart("1m", USD)).toBe("2026-08-26");
    expect(presetStart("6m", USD)).toBe("2026-03-26");
  });

  it("연 단위 프리셋을 환산한다", () => {
    expect(presetStart("1y", USD)).toBe("2025-09-26");
    expect(presetStart("5y", USD)).toBe("2021-09-26");
    expect(presetStart("10y", USD)).toBe("2016-09-26");
  });

  it("새로 더한 장기 프리셋을 환산한다", () => {
    // 2026-09-27 반복에서 추가됐다.
    expect(presetStart("20y", USD)).toBe("2006-09-26");
    expect(presetStart("30y", USD)).toBe("1996-09-26");
    expect(presetStart("40y", USD)).toBe("1986-09-26");
    expect(presetStart("50y", USD)).toBe("1976-09-26");
  });

  it("전체는 축적 시작일이다", () => {
    expect(presetStart("all", USD)).toBe("1964-05-04");
  });

  it("네 장기 프리셋이 서로 다른 구간을 만든다", () => {
    // 같은 값이 나오면 버튼이 넷인데 차트가 하나다.
    const starts = (["20y", "30y", "40y", "50y"] as const).map((p) =>
      presetStart(p, USD),
    );
    expect(new Set(starts).size).toBe(4);
  });
});

describe("축적 범위로 자르기", () => {
  it("축적 시작일보다 이르면 그 날짜로 자른다", () => {
    // FR-019 — EUR은 1994년부터다.
    expect(presetStart("40y", EUR)).toBe("1994-01-03");
    expect(presetStart("50y", EUR)).toBe("1994-01-03");
  });

  it("범위 안이면 자르지 않는다", () => {
    expect(presetStart("20y", EUR)).toBe("2006-09-26");
  });

  it("커버리지가 없으면 요청한 구간을 그대로 쓴다", () => {
    expect(presetStart("50y", null)).toBe("1976-09-26");
  });

  it("최초 제공일이 없으면 수집 시작일을 바닥으로 쓴다", () => {
    const partial: CoverageRow = { ...EUR, firstAvailableDate: null };
    expect(presetStart("50y", partial)).toBe("1994-01-03");
  });
});

describe("윤년 경계", () => {
  it("2월 29일에서 연 단위를 빼도 날짜가 깨지지 않는다", () => {
    vi.setSystemTime(new Date("2028-03-01T12:00:00Z")); // 어제 = 2028-02-29
    for (const preset of ["1y", "5y", "10y", "20y", "30y", "40y", "50y"] as const) {
      const start = presetStart(preset, null);
      expect(start).toMatch(/^\d{4}-\d{2}-\d{2}$/);
      // 존재하지 않는 2월 29일이 만들어지면 파싱이 다른 날짜로 흘러간다.
      expect(new Date(`${start}T00:00:00Z`).toISOString().slice(0, 10)).toBe(start);
    }
  });
});
