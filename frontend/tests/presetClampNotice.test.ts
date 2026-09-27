/**
 * 프리셋 클램프 알림 (T092) — 002 FR-019, SC-012.
 *
 * **FR-019의 "그 사실을 알려야 한다"가 구현되지 않은 채였다.** `RangeNotice`에
 * `clamped_to_coverage` 종류가 선언돼 있는데 그것을 만들어내는 코드가 어디에도 없었다.
 *
 * 최대가 10년일 때는 세 통화 모두 여유가 있어 드러나지 않았다. 20·30·40·50년을 더하면
 * EUR(1994~)에서 40년·50년·전체가 **같은 차트**를 그리면서 아무 설명이 없다. 오류도 나지
 * 않고 화면도 정상이라, 사용자는 버튼이 먹지 않는다고 여긴다.
 *
 * 반대로 잘리지 않았는데도 늘 알리면 안내가 배경 소음이 되어 진짜 잘린 경우를 가린다.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { presetClampNotice } from "@/stores/fxWorkspaceStore";
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
  vi.setSystemTime(new Date("2026-09-27T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

describe("잘렸을 때", () => {
  it("잘린 사실을 알린다", () => {
    const notice = presetClampNotice("50y", EUR);
    expect(notice?.kind).toBe("clamped_to_coverage");
  });

  it("어느 통화가 언제부터인지 밝힌다", () => {
    // "그 구간만 표시합니다"만으로는 왜 같은 차트인지 알 수 없다.
    const notice = presetClampNotice("40y", EUR);
    expect(notice?.message).toContain("EUR");
    expect(notice?.message).toContain("1994-01-03");
  });

  it("최초 제공일이 없으면 수집 시작일을 기준으로 알린다", () => {
    const partial: CoverageRow = { ...EUR, firstAvailableDate: null };
    expect(presetClampNotice("50y", partial)?.message).toContain("1994-01-03");
  });
});

describe("잘리지 않았을 때", () => {
  it("범위 안이면 알리지 않는다", () => {
    // SC-012 — 늘 알리면 안내가 배경 소음이 되어 진짜 잘린 경우를 가린다.
    expect(presetClampNotice("20y", EUR)).toBeNull();
    expect(presetClampNotice("1m", EUR)).toBeNull();
  });

  it("축적이 긴 통화는 장기 프리셋에서도 알리지 않는다", () => {
    for (const preset of ["20y", "30y", "40y", "50y"] as const) {
      expect(presetClampNotice(preset, USD)).toBeNull();
    }
  });

  it("전체는 잘림의 대상이 아니다", () => {
    // "전체"는 축적 시작일 그 자체라 잘릴 것이 없다.
    expect(presetClampNotice("all", EUR)).toBeNull();
    expect(presetClampNotice("all", USD)).toBeNull();
  });

  it("커버리지를 모르면 알리지 않는다", () => {
    // 아직 받지 못한 것과 잘린 것은 다르다. 모르는 상태로 단정하지 않는다.
    expect(presetClampNotice("50y", null)).toBeNull();
  });
});
