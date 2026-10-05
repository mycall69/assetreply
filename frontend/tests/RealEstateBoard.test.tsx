/**
 * 부동산 성과 보드 (T034) — 009 FR-006, FR-017, FR-018, FR-026, FR-029, FR-030, ui-wireframes E4.
 *
 * **부동산 전용 보드**다 — 칸이 여섯이라 `PerformanceBoard`(원금·수익·수익률)를 늘리지 않는다(research R9-10). 금액 형식은
 * `PerformanceBoard`와 **같은 함수**다 — 기호가 숫자 앞(`₩2,023,166,667`), 손실은 `-₩…`, 수익률은 부호와 함께(FR-029).
 *
 * - 매입가 칸 아래: 직접 넣었으면 "직접 입력", 아니면 쓴 창·건수(넓은 창이면 "추정") — 시세로 산 사실을 감추면 실제 매입가로 읽는다(FR-006)
 * - 평가액 칸 아래: 쓴 창·건수와 추정·잠정 글자(FR-017·FR-018·FR-030). 지금 시세가 없으면 0이 아니라 "—"(FR-026)
 * - 기준 줄: 어느 날짜까지 · 단지 · 평형 · 매입일 · 가정 넷(보유세 기준 비율과 서버의 가정 셋). 직접 넣은 매입가면 그 사실(FR-030) —
 *   가정이 보이지 않으면 실제 공시가격·단독 명의로 계산한 결과로 읽는다
 *
 * ## 이 테스트가 전제하는 모듈 (T039가 따른다)
 *
 * `@/components/realestate/RealEstateBoard` — `export function RealEstateBoard({ result })`
 * - `result: Omit<RealEstateSimulationResponse, "rows">` — 단지·평형·조건·취득 비용·요약
 * - 칸 여섯은 각각 `role="group"`과 칸 이름의 `aria-label`("매입가", "투입 금액", "누적 보유세", "평가액(지금 시세)", "투자 수익",
 *   "수익률") — 값과 그 아래 줄이 칸 안에 있다
 * - 기준 줄은 `<p>` 하나다(`PerformanceBoard`와 같다)
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RealEstateBoard } from "@/components/realestate/RealEstateBoard";
import { formatPercent } from "@/lib/format";
import type { RealEstateSimulationResponse } from "@/lib/types";
import { SIM_RESULT, SIM_SUMMARY } from "./support/realEstateSimulationFixtures";

const LABELS = ["매입가", "투입 금액", "누적 보유세", "평가액(지금 시세)", "투자 수익", "수익률"];

const cell = (name: string) => screen.getByRole("group", { name }).textContent ?? "";
/** 기준 줄 — 어느 날짜까지의 결과인지가 들어 있는 줄. */
const basisLine = () => screen.getByText(/2026-10-05/).closest("p")?.textContent ?? "";

function renderBoard(over: Partial<RealEstateSimulationResponse> = {}) {
  render(<RealEstateBoard result={{ ...SIM_RESULT, ...over }} />);
}

describe("칸 여섯", () => {
  it("매입가·투입 금액·누적 보유세·평가액·투자 수익·수익률 순서다", () => {
    renderBoard();
    expect(screen.getAllByRole("group").map((g) => g.getAttribute("aria-label"))).toEqual(LABELS);
  });

  it("금액은 기호가 숫자 앞이고 3자리마다 쉼표다", () => {
    renderBoard();
    expect(cell("매입가")).toContain("₩2,023,166,667");
    expect(cell("투입 금액")).toContain("₩2,108,139,667");
    expect(cell("누적 보유세")).toContain("₩32,428,400");
    expect(cell("평가액(지금 시세)")).toContain("₩2,450,000,000");
    expect(cell("투자 수익")).toContain("₩309,431,933");
  });

  it("수익률은 PerformanceBoard와 같은 형식이다 — 부호와 함께", () => {
    renderBoard();
    expect(cell("수익률")).toContain(formatPercent("0.146780"));
    expect(formatPercent("0.146780").startsWith("+")).toBe(true);
  });

  it("손실은 부호 → 기호 → 숫자다", () => {
    renderBoard({ summary: { ...SIM_SUMMARY, profit: "-84973000", returnRate: "-0.042000" } });
    expect(cell("투자 수익")).toContain("-₩84,973,000");
    expect(cell("수익률")).toContain("-4.20%");
  });

  it("투입 금액 아래에 매입가 + 취득 비용과 그 금액", () => {
    renderBoard();
    expect(cell("투입 금액")).toContain("매입가 + 취득 비용");
    expect(cell("투입 금액")).toContain("₩84,973,000");
  });

  it("누적 보유세 아래에 재산세·종부세를 따로", () => {
    renderBoard();
    expect(cell("누적 보유세")).toContain("재산세 ₩28,111,520");
    expect(cell("누적 보유세")).toContain("종부세 ₩4,316,880");
  });
});

describe("매입가 칸", () => {
  it("그 달 시세로 샀으면 그 사실과 건수", () => {
    renderBoard();
    const text = cell("매입가");
    expect(text).toContain("그 달 시세");
    expect(text).toContain("6건");
    expect(text).not.toContain("추정");
    expect(text).not.toContain("직접 입력");
  });

  it("넓힌 창의 시세로 샀으면 창·건수와 추정", () => {
    renderBoard({ condition: { ...SIM_RESULT.condition,
      buyPriceWindow: { months: 3, trades: 7, estimated: true } } });
    const text = cell("매입가");
    expect(text).toContain("3개월 평균");
    expect(text).toContain("7건");
    expect(text).toContain("추정");
  });

  it("직접 넣었으면 직접 입력 — 창·건수가 없다", () => {
    renderBoard({ condition: { ...SIM_RESULT.condition, buyPrice: "2000000000", buyPriceSource: "input",
      buyPriceWindow: null } });
    const text = cell("매입가");
    expect(text).toContain("직접 입력");
    expect(text).not.toMatch(/\d+건/);
  });
});

describe("평가액 칸", () => {
  it("지금 시세의 창·건수와 추정·잠정을 글자로", () => {
    renderBoard();
    const text = cell("평가액(지금 시세)");
    expect(text).toContain("3개월 평균");
    expect(text).toContain("41건");
    expect(text).toContain("추정");
    expect(text).toContain("잠정");
  });

  it("그 달 거래로 정한 확정 시세면 추정·잠정이 없다", () => {
    renderBoard({ summary: { ...SIM_SUMMARY, valueWindow: { months: 1, trades: 14 }, estimated: false,
      provisional: false } });
    const text = cell("평가액(지금 시세)");
    expect(text).toContain("그 달 시세");
    expect(text).toContain("14건");
    expect(text).not.toContain("추정");
    expect(text).not.toContain("잠정");
  });

  it("지금 시세가 없으면 0이 아니라 — 다", () => {
    renderBoard({ summary: { ...SIM_SUMMARY, value: null, valueMonth: null, valueWindow: null, estimated: false,
      provisional: false, lastPricedMonth: "2024-02" } });
    const text = cell("평가액(지금 시세)");
    expect(text).toContain("—");
    expect(text).not.toContain("₩");
  });

  it("시세가 있던 달이 하나도 없으면 투자 수익·수익률도 — 다", () => {
    renderBoard({ summary: { ...SIM_SUMMARY, value: null, valueMonth: null, valueWindow: null, estimated: false,
      provisional: false, profit: null, returnRate: null } });
    expect(cell("투자 수익")).toContain("—");
    expect(cell("투자 수익")).not.toContain("₩");
    expect(cell("수익률")).toContain("—");
    expect(cell("수익률")).not.toContain("%");
  });
});

describe("기준 줄 (FR-030)", () => {
  it("어느 날짜까지 · 단지 · 평형 · 매입일", () => {
    renderBoard();
    const line = basisLine();
    expect(line).toContain("2026-10-05 기준");
    expect(line).toContain("헬리오시티");
    expect(line).toContain("30평대(국평)");
    expect(line).toContain("2021-03-15 매입");
  });

  it("가정 넷 — 보유세 기준 비율과 서버가 준 가정 셋", () => {
    renderBoard();
    const line = basisLine();
    expect(line).toContain("보유세 기준 시세의 60%");
    for (const assumption of SIM_RESULT.condition.assumptions) expect(line).toContain(assumption);
  });

  it("보유세 기준 비율은 끝의 0을 지운 백분율이다", () => {
    renderBoard({ condition: { ...SIM_RESULT.condition, holdingTaxBaseRatio: "0.655000" } });
    expect(basisLine()).toContain("보유세 기준 시세의 65.5%");
  });

  it("매입가를 직접 넣었으면 그 사실을 더한다", () => {
    renderBoard({ condition: { ...SIM_RESULT.condition, buyPrice: "2000000000", buyPriceSource: "input",
      buyPriceWindow: null } });
    expect(basisLine()).toContain("매입가 직접 입력");
  });

  it("시세로 샀으면 매입가 직접 입력이 없다", () => {
    renderBoard();
    expect(basisLine()).not.toContain("직접 입력");
  });
});
