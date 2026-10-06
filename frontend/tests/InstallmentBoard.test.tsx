/**
 * 적금 보드 (011 T045) — FR-031, ui-wireframes §8.
 *
 * - 여섯 칸 — 총 납입 원금(낸 회차) · 세후 이자 합계(적금 · 예금) · 이자 소득세 합계 · 평가액(적금 · 예금) · 투자 수익 · 수익률
 * - 기준 줄 — 기준일 · 투자처 · 세율 · 지금 적금(가입일 · 금리 · 만기 · 낸 회차/12) · 지금 예금(가입일 · 금리)
 * - 화면은 계산하지 않는다 — 구성(적금 · 예금)도 서버 문자열이다
 * - 잠정·멈춤·확인 실패 알림은 `DepositNotice`를 그대로 쓴다. 잠정 문구는 지금 적금·지금 예금 가운데 잠정인 쪽의 대신 쓴 달과 금리를 밝힌다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DepositNotice } from "@/components/deposit/DepositNotice";
import { InstallmentBoard } from "@/components/deposit/InstallmentBoard";
import { SUMMARY } from "./support/installmentFixtures";

const cell = (label: string) => screen.getByRole("group", { name: label });

describe("적금 보드", () => {
  it("여섯 칸과 구성", () => {
    render(<InstallmentBoard summary={SUMMARY} institutionName="시중은행" taxRate="0.154000" />);
    expect(cell("총 납입 원금")).toHaveTextContent("₩37,000,000");
    expect(cell("총 납입 원금")).toHaveTextContent("37회 납입");
    expect(cell("세후 이자 합계")).toHaveTextContent("+₩811,149");
    expect(cell("세후 이자 합계")).toHaveTextContent("적금 ₩308,495 · 예금 ₩502,654");
    expect(cell("이자 소득세 합계")).toHaveTextContent("-₩147,654");
    expect(cell("평가액")).toHaveTextContent("₩37,811,149");
    expect(cell("평가액")).toHaveTextContent("적금 ₩1,000,000 · 예금 ₩36,811,149");
    expect(cell("투자 수익")).toHaveTextContent("+₩811,149");
    expect(cell("수익률")).toHaveTextContent("+2.19%");
  });

  it("기준 줄이 지금 적금과 지금 예금을 함께 보인다", () => {
    render(<InstallmentBoard summary={SUMMARY} institutionName="시중은행" taxRate="0.154000" />);
    const basis = screen.getByTestId("installment-basis");
    expect(basis).toHaveTextContent("2018-01-15 기준 · 시중은행 · 세율 15.4%");
    expect(basis).toHaveTextContent("지금 적금 2018-01-15 가입 · 1.82% · 만기 2019-01-15(1/12회)");
    expect(basis).toHaveTextContent("지금 예금 2018-01-15 가입 · 1.93%");
  });

  it("손실이면 부호와 색이 함께 바뀐다", () => {
    render(<InstallmentBoard summary={{ ...SUMMARY, profit: "-444000", returnRate: "-0.012000" }}
      institutionName="시중은행" taxRate="0.154000" />);
    expect(cell("투자 수익")).toHaveTextContent("-₩444,000");
    expect(cell("수익률")).toHaveTextContent("-1.20%");
  });

  it("멈췄으면 진행 중인 계약이 없다고 기준 줄이 말하지 않는다", () => {
    render(<InstallmentBoard summary={{ ...SUMMARY, currentInstallment: null, currentDeposit: null, isFinal: false,
      stopped: { date: "2016-01-15", reason: "rate_missing", month: "2016-01" } }}
      institutionName="시중은행" taxRate="0.154000" />);
    const basis = screen.getByTestId("installment-basis");
    expect(basis).not.toHaveTextContent("지금 적금");
    expect(basis).not.toHaveTextContent("지금 예금");
  });
});

describe("적금 안내 줄", () => {
  it("잠정이면 잠정인 쪽의 대신 쓴 달과 금리를 밝힌다", () => {
    render(<DepositNotice start="2015-01-15" summary={{ ...SUMMARY, provisionalFrom: "2026-01-15",
      currentInstallment: { ...SUMMARY.currentInstallment!, rate: "2.94", rateMonth: "2026-08", provisional: true },
      currentDeposit: { ...SUMMARY.currentDeposit!, rate: "3.39", rateMonth: "2026-08", provisional: true } }} />);
    const line = screen.getByRole("status");
    expect(line).toHaveTextContent("잠정 — 2026-01-15 가입 금리가 아직 발표되지 않아");
    expect(line).toHaveTextContent("지금 적금 2026-08 금리(2.94%)");
    expect(line).toHaveTextContent("지금 예금 2026-08 금리(3.39%)");
    expect(line).toHaveTextContent("금리가 발표되면 값이 바뀝니다");
  });

  it("멈춤은 008과 같은 문장이다", () => {
    render(<DepositNotice start="2015-01-15" summary={{ ...SUMMARY, currentInstallment: null, currentDeposit: null,
      stopped: { date: "2016-01-15", reason: "rate_missing", month: "2016-01" } }} />);
    expect(screen.getByRole("status")).toHaveTextContent(
      "2016-01 금리 통계가 비어 있어 2016-01-15 만기에서 계산을 멈췄습니다");
  });
});
