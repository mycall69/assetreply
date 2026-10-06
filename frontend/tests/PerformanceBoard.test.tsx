/**
 * 성과 보드 (T033) — 005 FR-031, FR-032, SC-013.
 *
 * **보드의 수치와 표 마지막 행의 수치가 같아야 한다.** 어긋나면 사용자는 어느 쪽이
 * 맞는지 알 수 없다.
 */
// 012 승인 2026-10-06 — 고정 행의 종류 이름 month_first → period(012 FR-008). 단언은 그대로다.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import type { SimulationRow, SimulationSummary } from "@/lib/types";

const summary: SimulationSummary = {
  principal: "86997", profit: "120777", returnRate: "1.388300",
  asOf: "2024-08-01", isFinal: true,
};

const latest: SimulationRow = {
  date: "2024-08-01", kind: "period", openPrice: "201500", closePrice: "201500",
  boughtShares: 0, heldShares: 1, cash: "6274", principal: "86997",
  balance: "201500", profit: "120777", returnRate: "1.388300",
};

const props = { summary, currency: "KRW", exchange: undefined };

describe("성과 보드", () => {
  it("투자 원금·수익·수익률을 보여준다", () => {
    render(<PerformanceBoard {...props} />);
    expect(screen.getByText(/86,997/)).toBeInTheDocument();
    expect(screen.getByText(/120,777/)).toBeInTheDocument();
    expect(screen.getByText(/138\.83%/)).toBeInTheDocument();
  });

  it("기준 구간이 함께 드러난다", () => {
    // FR-031 — 어느 날짜까지의 결과인지 알 수 없으면 오늘까지로 읽는다.
    render(<PerformanceBoard {...props} />);
    expect(screen.getByText(/2024-08-01/)).toBeInTheDocument();
  });

  it("기준 통화를 밝힌다", () => {
    // SC-019 — 밝히지 않으면 사용자가 어느 쪽을 보는지 모른다.
    render(<PerformanceBoard {...props} />);
    expect(screen.getByText(/KRW/)).toBeInTheDocument();
  });

  it("보드와 표 마지막 행의 수치가 같다", () => {
    // SC-013 — 어긋나면 어느 쪽이 맞는지 알 수 없다.
    expect(summary.profit).toBe(latest.profit);
    expect(summary.returnRate).toBe(latest.returnRate);
    expect(summary.principal).toBe(latest.principal);
  });

  it("수익이 음수면 부호로도 드러난다", () => {
    render(
      <PerformanceBoard
        {...props}
        summary={{ ...summary, profit: "-5446", returnRate: "-0.062600" }}
      />,
    );
    // 007 FR-042a(반복 2026-10-04) — 기호가 숫자 앞이라 부호와 숫자 사이에 기호가 온다(`-₩5,446`). 사용자 승인(D2).
    expect(screen.getByText(/-₩5,446|−₩5,446/)).toBeInTheDocument();
    expect(screen.getByText(/-6\.26%|−6\.26%/)).toBeInTheDocument();
  });
});
