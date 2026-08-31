/**
 * 요약 카드 테스트 (T024) — contracts/ui-wireframes.md W2.
 *
 * FR-013: 상승·하락을 방향 기호와 색으로 **함께** 구분한다. 색 하나에만 의존하면
 * 색각 이상 사용자가 읽을 수 없다.
 * FR-014: 잠정인지 확정인지 값 근처에서 드러나야 한다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RateSummary } from "@/components/fx/RateSummary";
import type { LatestResponse } from "@/lib/types";

const CONFIRMED: LatestResponse = {
  currency: "USD", quotePair: "USD/KRW", date: "2026-08-29",
  baseRate: "1356.100000", quoteUnit: 1, isProvisional: false, fetchedAt: null,
  change: { comparedTo: "2026-08-28", absolute: "-3.900000", percent: "-0.29", direction: "down" },
};

const PROVISIONAL: LatestResponse = {
  ...CONFIRMED, date: "2026-08-30", baseRate: "1354.200000",
  isProvisional: true, fetchedAt: "2026-08-30T14:23:11Z",
};

describe("요약 카드", () => {
  it("통화쌍과 기준 날짜를 함께 밝힌다", () => {
    render(<RateSummary latest={CONFIRMED} />);
    expect(screen.getByText(/USD\/KRW/)).toBeInTheDocument();
    expect(screen.getByText(/2026-08-29/)).toBeInTheDocument();
  });

  it("매매기준율을 표시한다", () => {
    render(<RateSummary latest={CONFIRMED} />);
    expect(screen.getByText("1,356.10")).toBeInTheDocument();
  });

  it("변화량을 절대값과 백분율로 함께 보여준다", () => {
    render(<RateSummary latest={CONFIRMED} />);
    const change = screen.getByTestId("change");
    expect(change.textContent).toContain("3.90");
    expect(change.textContent).toContain("0.29%");
  });

  it("방향을 색이 아닌 기호로도 구분한다", () => {
    render(<RateSummary latest={CONFIRMED} />);
    expect(screen.getByTestId("change").textContent).toMatch(/[▼▲]/);
  });

  it("확정값에는 잠정 배지가 없다", () => {
    render(<RateSummary latest={CONFIRMED} />);
    expect(screen.queryByText(/잠정/)).toBeNull();
    expect(screen.getByText(/확정/)).toBeInTheDocument();
  });

  it("잠정값은 배지와 갱신 시각을 함께 표시한다", () => {
    render(<RateSummary latest={PROVISIONAL} />);
    expect(screen.getByText(/잠정/)).toBeInTheDocument();
    expect(screen.getByTestId("summary-meta").textContent).toContain("2026-08-30");
  });

  it("데이터가 없으면 안내한다", () => {
    render(<RateSummary latest={{ ...CONFIRMED, status: "no_data", baseRate: null, date: null, change: null }} />);
    expect(screen.getByText(/수집된 데이터가 없습니다/)).toBeInTheDocument();
  });
});
