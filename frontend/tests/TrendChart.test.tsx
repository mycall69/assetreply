/**
 * 추이 차트 테스트 (T037) — FR-016, FR-017a, FR-018, SC-007a.
 *
 * 캔버스 렌더링은 검증 대상이 아니다. **무엇을 알리는가**를 본다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TrendChart } from "@/components/fx/TrendChart";
import type { SeriesResponse } from "@/lib/types";

vi.mock("@/components/FxChart", () => ({
  FxChart: () => <div data-testid="chart" />,
}));

const SERIES: SeriesResponse = {
  currency: "USD", quoteUnit: 1, from: "2026-08-01", to: "2026-08-30",
  algorithm: "lttb",
  points: [
    { date: "2026-08-14", baseRate: "1372.300000" },
    { date: "2026-08-29", baseRate: "1356.100000" },
    { date: "2026-08-30", baseRate: "1354.200000", isProvisional: true },
  ],
  gaps: [{ from: "2026-08-15", to: "2026-08-28", reason: "no_quote" }],
  downsampled: false,
  sourcePointCount: 3,
};

const base = { collecting: null, loading: false, onSelect: vi.fn() };

describe("추이 차트", () => {
  it("선택 날짜와 그 값을 라벨로 표시한다", () => {
    render(<TrendChart {...base} series={SERIES} selectedDate="2026-08-29" />);
    const label = screen.getByTestId("highlight-label");
    expect(label.textContent).toContain("2026-08-29");
    expect(label.textContent).toContain("1,356.10");
  });

  it("선택 날짜에 고시가 없으면 그 사실을 알린다", () => {
    render(<TrendChart {...base} series={SERIES} selectedDate="2026-08-20" />);
    expect(screen.getByText(/이 날짜에는 고시가 없습니다/)).toBeInTheDocument();
  });

  it("잠정 구간을 범례로 구분한다", () => {
    render(<TrendChart {...base} series={SERIES} selectedDate={null} />);
    expect(screen.getByTestId("provisional-legend").textContent).toContain("잠정");
  });

  it("차트의 마지막 시점이 잠정값을 포함한다", () => {
    /** SC-007a: 요약(오늘)과 차트(어제)의 끝점이 어긋나면 안 된다. */
    const last = SERIES.points[SERIES.points.length - 1];
    expect(last.date).toBe("2026-08-30");
    expect(last.isProvisional).toBe(true);
  });

  it("선택 날짜가 기간 밖이면 안내하고 날짜를 바꾸지 않는다", () => {
    render(<TrendChart {...base} series={SERIES} selectedDate="2019-01-01" />);
    expect(screen.getByText(/현재 기간 밖입니다/)).toBeInTheDocument();
    expect(screen.queryByTestId("highlight-label")).toBeNull();
  });

  it("수집 중이면 그 사실을 알린다", () => {
    render(
      <TrendChart {...base} series={null} selectedDate={null}
        collecting={{ status: "collecting", currency: "USD", from: "2026-08-01", to: "2026-08-30", missingDays: 100 }} />,
    );
    expect(screen.getByRole("status").textContent).toContain("수집을 시작했습니다");
  });

  it("결측 구간 정보를 범례에 밝힌다", () => {
    render(<TrendChart {...base} series={SERIES} selectedDate={null} />);
    expect(screen.getByText(/고시 없음/)).toBeInTheDocument();
  });
});
