/**
 * 부동산 보드의 매도비용 (010 반복 5, T078) — FR-031, ui-wireframes F8.
 *
 * - 보드가 **매입가 · 투입 금액 · 누적 보유세 · 평가액 · 매도비용 · 투자 수익 · 수익률** 일곱이다. 투자 수익·수익률은 매도비용을 뺀 값이고 보유 중 값이
 *   함께 보인다 — 보드가 월별 표의 마지막 행과 다른 까닭이 보여야 한다
 * - 매도비용 칸은 중개 보수·양도소득세(지방소득세 포함)와 판정(비과세·고가주택·요건 밖·단기·차익 없음)·장특공·보유·거주 연수
 * - 규칙 표 밖은 세금이 `—`와 사유이고 투자 수익·수익률은 보유 중 값(0을 빼지 않는다 — 헌법 원칙 V)
 * - 기준 줄에 1세대 1주택·부부 5:5·거주 기간 비율. `saleCost`가 없으면(시세 없음, 반복 5 전 형식) 여섯 칸 그대로
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RealEstateBoard } from "@/components/realestate/RealEstateBoard";
import type { RealEstateSaleCost, RealEstateSimulationResponse } from "@/lib/types";
import { SIM_RESULT, SIM_SUMMARY } from "./support/realEstateSimulationFixtures";

const HIGH: RealEstateSaleCost = {
  brokerage: "17150000", incomeTax: "21000000", localTax: "2100000", total: "40250000", kind: "high_price",
  gain: "380000000", taxableGain: "193877551", ltsdRate: "0.400000", holdingYears: 5, residenceYears: 5,
  basePerOwner: "55663265",
};

function withSale(saleCost: RealEstateSaleCost, after: { profit: string | null; rate: string | null } =
  { profit: "269181933", rate: "0.127687" }): RealEstateSimulationResponse {
  return {
    ...SIM_RESULT,
    condition: { ...SIM_RESULT.condition, residenceRatio: "1.000000" },
    summary: { ...SIM_SUMMARY, saleCost, profitAfterSale: after.profit, returnRateAfterSale: after.rate },
  };
}

const groups = () => screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"));
const group = (name: string) => screen.getByRole("group", { name });

describe("부동산 보드의 매도비용", () => {
  it("일곱 칸이다 — 평가액 다음에 매도비용", () => {
    render(<RealEstateBoard result={withSale(HIGH)} />);
    expect(groups()).toEqual(["매입가", "투입 금액", "누적 보유세", "평가액(지금 시세)", "매도비용", "투자 수익", "수익률"]);
  });

  it("매도비용 칸은 합계와 중개 보수·양도소득세·판정", () => {
    render(<RealEstateBoard result={withSale(HIGH)} />);
    const sale = group("매도비용");
    expect(sale).toHaveTextContent("-₩40,250,000");
    expect(sale).toHaveTextContent("중개 보수 ₩17,150,000");
    expect(sale).toHaveTextContent("양도소득세 ₩23,100,000 (지방소득세 포함)");
    expect(sale).toHaveTextContent("고가주택(12억 초과분) · 장특공 40% · 보유 5년 · 거주 5년");
  });

  it("투자 수익·수익률은 매도비용을 뺀 값이고 보유 중 값을 함께 보인다", () => {
    render(<RealEstateBoard result={withSale(HIGH)} />);
    expect(group("투자 수익")).toHaveTextContent("₩269,181,933");
    expect(group("투자 수익")).toHaveTextContent("매도비용을 뺀 값");
    expect(group("투자 수익")).toHaveTextContent("보유 중 ₩309,431,933");
    expect(group("수익률")).toHaveTextContent("+12.76%");
    expect(group("수익률")).toHaveTextContent("보유 중 +14.67%");
    expect(screen.getByText(/1세대 1주택 · 부부 5:5 · 거주 기간 = 보유 × 100%/)).toBeInTheDocument();
  });

  it.each([
    [{ ...HIGH, kind: "exempt", incomeTax: "0", localTax: "0", total: "17150000" } as RealEstateSaleCost, "비과세(12억 이하)"],
    [{ ...HIGH, kind: "taxed", ltsdRate: "0.100000", residenceYears: 1 } as RealEstateSaleCost,
      "비과세 요건 밖(거주 2년 미만) · 장특공 10% · 보유 5년 · 거주 1년"],
    [{ ...HIGH, kind: "short_term", ltsdRate: "0.000000", holdingYears: 1, residenceYears: 1 } as RealEstateSaleCost,
      "단기 보유 — 세율 60%"],
    [{ ...HIGH, kind: "short_term", ltsdRate: "0.000000", holdingYears: 0, residenceYears: 0 } as RealEstateSaleCost,
      "단기 보유 — 세율 70%"],
    [{ ...HIGH, kind: "no_gain", incomeTax: "0", localTax: "0", total: "17150000" } as RealEstateSaleCost, "양도차익 없음"],
  ])("판정 — %#", (cost, text) => {
    render(<RealEstateBoard result={withSale(cost)} />);
    expect(group("매도비용")).toHaveTextContent(text);
  });

  it("규칙 표 밖 — 세금은 —와 사유, 투자 수익·수익률은 보유 중 값", () => {
    const outside = { ...HIGH, kind: "outside_table", incomeTax: null, localTax: null, total: null } as RealEstateSaleCost;
    render(<RealEstateBoard result={withSale(outside, { profit: null, rate: null })} />);
    expect(group("매도비용")).toHaveTextContent("—");
    expect(group("매도비용")).toHaveTextContent("세금 — 규칙 표 밖(2023-01-01 앞)");
    expect(group("투자 수익")).toHaveTextContent("₩309,431,933");
    expect(group("투자 수익")).toHaveTextContent("매도 세금을 모름 — 보유 중 값");
    expect(group("수익률")).toHaveTextContent("+14.67%");
  });

  it("saleCost가 없으면 여섯 칸 그대로", () => {
    render(<RealEstateBoard result={SIM_RESULT} />);
    expect(groups()).toEqual(["매입가", "투입 금액", "누적 보유세", "평가액(지금 시세)", "투자 수익", "수익률"]);
    expect(screen.queryByText(/거주 기간 = 보유/)).toBeNull();
  });
});
