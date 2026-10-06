/**
 * 가상자산 일자별 투자 성과 표 (T028) — 007 FR-037~FR-041, SC-009, SC-010, ui-wireframes C4.
 *
 * - **배당 열이 없다**(FR-037) — 주식 표를 그대로 쓰면 빈 열 다섯이 1440px을 차지한다
 * - 통화는 열 이름 아래 줄(006 R6-26). 잔고 괄호는 KRW, 투자 수익·수익율은 KRW 기준(FR-035)
 * - 수량은 소수 8자리, 매매 수수료는 매수 행에만(FR-026, FR-027)
 * - 012 승인 2026-10-06 — `◇`(그 달 1일 결측)는 없어졌다. 결측은 일 단위의 결측 구간 행이 드러낸다(FR-004b·FR-008)
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CryptoPerformanceTable } from "@/components/crypto/CryptoPerformanceTable";
import { BUY_ROW, LATEST_ROW, MISSING_ROW, RESULT, TINY_ROW } from "./support/cryptoFixtures";

vi.mock("@/hooks/useInfiniteScroll", () => ({ useInfiniteScroll: () => () => undefined }));

function renderTable(rows = RESULT.rows, currency = "USD") {
  return render(
    <CryptoPerformanceTable rows={rows} currency={currency} quoteCurrency="USD"
      summary={RESULT.summary} hasMore={false} onLoadMore={() => undefined} />);
}

const headers = () => screen.getAllByRole("columnheader");
/** 날짜로 행을 찾는다 — 날짜 글자는 표 아래 상태 줄에도 나오므로 행의 첫 칸으로 찾는다. */
const cellsOf = (date: string) => {
  const row = screen.getAllByRole("row").find((r) =>
    (within(r).queryAllByRole("cell")[0]?.textContent ?? "").startsWith(date)) as HTMLElement;
  return within(row).getAllByRole("cell").map((c) => c.textContent ?? "");
};

describe("열", () => {
  it("배당 열 없이 11개 열이다", () => {
    renderTable();
    const names = headers().map((h) => (h.textContent ?? "").replace(/\(.*\)/, "").trim());
    expect(names).toEqual([
      "날짜", "시가", "구매 수량", "매매 수수료", "보유 수량", "예수금", "투자금", "잔고",
      "투자 수익", "수익율", "환율"]);
    expect(screen.queryByText(/배당/)).toBeNull();
  });

  it("머리글의 통화는 열 이름 아래 줄이다", () => {
    renderTable();
    const unit = (name: string) => {
      const header = headers().find((h) => (h.textContent ?? "").startsWith(name)) as HTMLElement;
      return header.querySelector("span.block")?.textContent ?? null;
    };
    expect(unit("시가")).toBe("(USD)");
    expect(unit("매매 수수료")).toBe("(USD)");
    expect(unit("예수금")).toBe("(USD)");
    expect(unit("투자금")).toBe("(USD)");
    expect(unit("잔고")).toBe("(USD · KRW)");
    expect(unit("투자 수익")).toBe("(KRW)");
    expect(unit("수익율")).toBe("(KRW 기준)");
  });

  it("원화 원금이면 투자금 열이 KRW다", () => {
    renderTable(RESULT.rows, "KRW");
    const header = headers().find((h) => (h.textContent ?? "").startsWith("투자금")) as HTMLElement;
    expect(header.querySelector("span.block")?.textContent).toBe("(KRW)");
  });

  it("표는 내용 폭이다", () => {
    renderTable();
    expect(screen.getByRole("table").className).toContain("w-max");
  });
});

describe("행", () => {
  it("매수 행 — 수량 8자리, 수수료, 잔고 USD (KRW)", () => {
    renderTable();
    const cells = cellsOf(BUY_ROW.date);
    expect(cells[1]).toBe("7,196.39");
    expect(cells[2]).toBe("1.38819719");
    expect(cells[3]).toBe("9.99");
    expect(cells[4]).toBe("1.38819719");
    expect(cells[7]).toBe("9,990.00 (11,557,841)");
    expect(cells[8]).toBe("-12,159");
    expect(cells[9]).toBe("-0.10%");
  });

  it("매수가 없는 행은 구매 수량 0이고 수수료 칸이 비었다", () => {
    renderTable();
    const cells = cellsOf(LATEST_ROW.date);
    expect(cells[2]).toBe("0");
    expect(cells[3]).toBe("");
  });

  it("1일 결측은 결측 구간 행이 드러내고 ◇가 없다", () => {
    // 012 승인 2026-10-06 — ◇(firstDayMissing) 대신 일 단위의 결측 구간 행이다(FR-004b·FR-008).
    renderTable([LATEST_ROW, MISSING_ROW, { kind: "missing", date: "2021-03-01", dateTo: "2021-03-01" }, BUY_ROW]);
    const gap = screen.getAllByRole("row").find((r) => r.getAttribute("data-kind") === "missing") as HTMLElement;
    expect(gap).toHaveTextContent("2021-03-01 출처 결측 — 값 없음");
    expect(gap.closest("tbody")?.textContent).toContain(MISSING_ROW.date);
    expect(screen.queryAllByText("◇")).toHaveLength(0);
  });

  it("아주 작은 시가도 유효 숫자로 보인다", () => {
    renderTable([TINY_ROW]);
    const cells = cellsOf(TINY_ROW.date);
    expect(cells[1]).toBe("0.000005299");
    expect(cells[4]).toBe("1,886,792,452.83018868");
  });

  it("환율 칸은 그 행의 매매기준율이고 날짜가 다르면 알린다", () => {
    renderTable();
    expect(cellsOf(BUY_ROW.date)[10]).toContain("1,156.40");
    expect(screen.getByRole("img", { name: /2020-01-01에 환율 고시가 없어 2019-12-31/ }))
      .toBeInTheDocument();
  });
});
