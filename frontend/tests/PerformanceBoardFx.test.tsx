/**
 * 외화 종목의 보드 (T072) — 005 FR-021, FR-041, SC-009, SC-019.
 *
 * **기준 통화를 밝힌다.** 밝히지 않으면 사용자는 달러 기준 수익률로 읽는다 — 둘은
 * 환율 변동만큼 다르다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { ExchangeInfo, SimulationSummary } from "@/lib/types";

const summary: SimulationSummary = {
  principal: "1000000", profit: "212400", returnRate: "0.212400",
  asOf: "2024-08-01", isFinal: true,
};

const exchange: ExchangeInfo = {
  rate: "1302.275000", rateDate: "2021-08-02",
  kind: "cash_buy_discounted", spreadDiscount: "0.9",
};

describe("외화 종목의 보드", () => {
  it("적용 환율과 날짜가 드러난다", () => {
    // SC-009 — 어느 환율로 환전됐는지 알 수 없으면 검산할 수 없다.
    render(
      <PerformanceBoard summary={summary} currency="KRW" exchange={exchange} />,
    );
    expect(screen.getByText(/1,302\.27|1302\.27/)).toBeInTheDocument();
    expect(screen.getByText(/2021-08-02/)).toBeInTheDocument();
  });

  it("우대가 적용됐음이 드러난다", () => {
    render(
      <PerformanceBoard summary={summary} currency="KRW" exchange={exchange} />,
    );
    expect(screen.getByText(/우대/)).toBeInTheDocument();
  });

  it("기준 통화를 밝힌다", () => {
    // SC-019 — 원금 통화 기준임을 밝히지 않으면 어느 쪽을 보는지 모른다.
    render(
      <PerformanceBoard summary={summary} currency="KRW" exchange={exchange} />,
    );
    expect(screen.getByText(/KRW 기준/)).toBeInTheDocument();
  });

  it("환전이 없으면 환율 줄이 없다", () => {
    render(<PerformanceBoard summary={summary} currency="KRW" />);
    expect(screen.queryByText(/우대/)).toBeNull();
  });

  it("시작일과 환율 날짜가 다를 수 있다", () => {
    // FR-022 — 2021-08-01은 일요일이라 그날 환율이 없다.
    render(
      <PerformanceBoard summary={summary} currency="KRW" exchange={exchange} />,
    );
    expect(screen.getByText(/2021-08-02/)).toBeInTheDocument();
  });
});
