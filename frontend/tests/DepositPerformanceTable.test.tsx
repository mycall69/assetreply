/**
 * 예금 일자별 투자 성과 표 (T016) — 008 FR-032~FR-034, ui-wireframes D4.
 *
 * - 열 10개, 금액 열의 통화는 머리글 아래 줄(006 R6-26)
 * - **구분은 글자**다 — 가입·월·만기·재예치, 잠정이면 "·잠정"(색만으로 전달하지 않는다, FR-033)
 * - 적용 금리 칸은 금리와 그 달, 잠정이면 "(26-08 대신)" — 대신 쓴 달을 밝힌다
 * - 월 행의 이자는 **경과분**이다 — 머리글 도움말로 밝힌다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DepositPerformanceTable } from "@/components/deposit/DepositPerformanceTable";
import type { DepositRow } from "@/lib/types";
import { PROVISIONAL, ROWS } from "./support/depositFixtures";

const headers = () => screen.getAllByRole("columnheader");
/** 머리글의 이름 — 통화 줄(`span.block`)을 뺀 글자. "이자(세전)"의 괄호는 이름의 일부다. */
const nameOf = (h: HTMLElement) =>
  (h.textContent ?? "").replace(h.querySelector("span.block")?.textContent ?? "\u0000", "").trim();
const bodyRows = () => screen.getAllByRole("row").slice(1);
const cells = (row: HTMLElement) => within(row).getAllByRole("cell").map((c) => c.textContent ?? "");

describe("열", () => {
  it("열 10개", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    expect(headers().map(nameOf)).toEqual([
      "날짜", "구분", "적용 금리", "예치 원금", "이자(세전)", "이자 소득세", "세후 이자", "잔고", "투자 수익", "수익률"]);
  });

  it("금액 열의 통화는 머리글 아래 줄이다", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    const units = headers().map((h) => h.querySelector("span.block")?.textContent ?? null);
    expect(units).toEqual([null, null, null, "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", null]);
  });

  it("이자 머리글이 월 행은 경과분이라고 밝힌다", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    const interest = headers().find((h) => nameOf(h) === "이자(세전)") as HTMLElement;
    expect(interest.getAttribute("title")).toMatch(/경과분/);
    expect(interest.getAttribute("title")).toMatch(/만기/);
  });

  it("표는 내용 폭이다", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    expect(screen.getByRole("table").className).toContain("w-max");
  });
});

describe("행", () => {
  it("최신순이고 구분은 글자다", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    expect(bodyRows().map((r) => cells(r).slice(0, 2))).toEqual([
      ["2026-10-01", "월"], ["2026-01-15", "재예치"], ["2026-01-15", "만기"], ["2020-01-15", "가입"]]);
  });

  it("월 행 — 금리와 그 달, 원 단위 쉼표, 부호 있는 수익률", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    expect(cells(bodyRows()[0])).toEqual([
      "2026-10-01", "월", "2.84% (26-01)", "11,361,267", "228,955", "35,259", "193,696", "11,554,963",
      "1,554,963", "+15.54%"]);
  });

  it("만기 행은 만기 이자, 가입 행은 0", () => {
    render(<DepositPerformanceTable rows={ROWS} />);
    expect(cells(bodyRows()[2]).slice(2, 7)).toEqual(["3.06% (25-01)", "11,074,573", "338,881", "52,187", "286,694"]);
    expect(cells(bodyRows()[3]).slice(4, 10)).toEqual(["0", "0", "0", "10,000,000", "0", "+0.00%"]);
  });

  it("금리는 출처 문자열이라 끝의 0이 없을 수 있다 — 두 자리로 보인다", () => {
    const row: DepositRow = { ...ROWS[0], rate: "3.2", rateMonth: "2024-03" };
    render(<DepositPerformanceTable rows={[row]} />);
    expect(cells(bodyRows()[0])[2]).toBe("3.20% (24-03)");
  });

  it("잠정이면 구분에 ·잠정, 금리 칸에 대신 쓴 달", () => {
    render(<DepositPerformanceTable rows={PROVISIONAL.rows} />);
    expect(cells(bodyRows()[1]).slice(0, 3)).toEqual(["2026-09-15", "가입·잠정", "3.39% (26-08 대신)"]);
    expect(cells(bodyRows()[0])[1]).toBe("월·잠정");
  });

  it("손실이면 음수 부호", () => {
    const row: DepositRow = { ...ROWS[0], profit: "-12", returnRate: "-0.000001" };
    render(<DepositPerformanceTable rows={[row]} />);
    expect(cells(bodyRows()[0]).slice(8)).toEqual(["-12", "-0.00%"]);
  });
});
