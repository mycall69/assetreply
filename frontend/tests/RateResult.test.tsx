/**
 * 조회 결과 렌더 구분 테스트 (T043).
 *
 * contracts/ui-sketches.md S1/S2 — `no_quote`일 때 주 결과 영역에 숫자가 없어야 하고
 * 참고 정보가 시각적으로 분리되어야 한다 (헌법 원칙 V, FR-018a/b).
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RateResult } from "@/components/RateResult";
import type { RateQuoted, RateNoQuote } from "@/lib/types";

const QUOTED: RateQuoted = {
  status: "quoted",
  currency: "USD",
  date: "2005-03-15",
  quoteUnit: 1,
  baseRate: "1012.30",
  derived: {
    cashBuy: "1014.12",
    cashSell: "1010.48",
    remitSend: "1012.81",
    remitReceive: "1011.79",
  },
  appliedSpread: {
    cashBuy: "0.001800",
    cashSell: "0.001800",
    remitSend: "0.000500",
    remitReceive: "0.000500",
  },
  spreadBasis: "current",
  source: "ECOS:731Y001",
};

const NO_QUOTE: RateNoQuote = {
  status: "no_quote",
  currency: "USD",
  date: "2005-03-19",
  message: "해당일에는 고시가 없습니다.",
  reference: {
    kind: "previous_business_day",
    date: "2005-03-18",
    quoteUnit: 1,
    baseRate: "1010.90",
    note: "요청하신 2005-03-19의 값이 아닙니다.",
  },
};

describe("고시가 있는 날", () => {
  it("매매기준율을 주 결과로 표시한다", () => {
    render(<RateResult result={QUOTED} />);
    const main = screen.getByTestId("primary-result");
    expect(within(main).getByText(/1,012\.30/)).toBeInTheDocument();
  });

  it("출처를 표시한다", () => {
    render(<RateResult result={QUOTED} />);
    expect(screen.getByText(/ECOS:731Y001/)).toBeInTheDocument();
  });

  it("파생 환율 4종을 표시한다", () => {
    render(<RateResult result={QUOTED} />);
    const derived = screen.getByTestId("derived-rates");
    for (const label of ["현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때"]) {
      expect(within(derived).getByText(label)).toBeInTheDocument();
    }
    expect(within(derived).getByText("1,014.12")).toBeInTheDocument();
  });

  it("현재 스프레드를 적용한 결과임을 밝힌다", () => {
    render(<RateResult result={QUOTED} />);
    expect(screen.getByText(/현재 설정된 스프레드/)).toBeInTheDocument();
  });

  it("JPY는 100엔 단위를 함께 표시한다", () => {
    render(<RateResult result={{ ...QUOTED, currency: "JPY", quoteUnit: 100,
      baseRate: "1102.45" }} />);
    expect(screen.getByTestId("primary-result").textContent).toMatch(/100엔/);
  });
});

describe("고시가 없는 날", () => {
  it("주 결과 영역에 숫자가 없다", () => {
    render(<RateResult result={NO_QUOTE} />);
    const main = screen.getByTestId("primary-result");
    expect(main.textContent ?? "").not.toMatch(/\d{3}/);
  });

  it("고시 없음을 알린다", () => {
    render(<RateResult result={NO_QUOTE} />);
    expect(screen.getByText(/고시가 없습니다/)).toBeInTheDocument();
  });

  it("참고 정보가 별도 영역으로 분리된다", () => {
    render(<RateResult result={NO_QUOTE} />);
    const ref = screen.getByTestId("reference-block");
    expect(within(ref).getByText(/1,010\.90/)).toBeInTheDocument();
    expect(ref).not.toBe(screen.getByTestId("primary-result"));
  });

  it("참고값이 요청일 값이 아님을 경고한다", () => {
    render(<RateResult result={NO_QUOTE} />);
    const ref = screen.getByTestId("reference-block");
    expect(within(ref).getByText(/값이 아닙니다/)).toBeInTheDocument();
  });

  it("파생 환율 4종을 참고 영역에 표시하지 않는다", () => {
    render(<RateResult result={NO_QUOTE} />);
    const ref = screen.getByTestId("reference-block");
    for (const label of ["현금 살 때", "현금 팔 때", "송금 보낼 때", "송금 받을 때"]) {
      expect(within(ref).queryByText(label)).toBeNull();
    }
  });

  it("참고가 없으면 참고 영역도 없다", () => {
    render(<RateResult result={{ ...NO_QUOTE, reference: null }} />);
    expect(screen.queryByTestId("reference-block")).toBeNull();
  });
});
