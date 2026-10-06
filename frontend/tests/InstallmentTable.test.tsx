/**
 * 적금 표 (011 T045) — FR-032, ui-wireframes §8.
 *
 * - 열 — 날짜 · 구분 · 회차 · 적용 금리 · 금액 · 이자(세전) · 이자 소득세 · 세후 이자 · 적금 평가 · 예금 평가 · 평가액 · 투자 수익 · 수익률
 * - 구분은 글자다 — 납입 · 월 · 적금 만기 · 예금 만기 · 예금 가입, 잠정이면 "·잠정"(색만으로 전달하지 않는다)
 * - 납입 행의 회차는 "n/12"다. 적용 금리는 그 금리의 달이고, 잠정이면 "(26-08 대신)"이다(008 `rateCell`)
 * - 예금 가입 행의 금액 `title`이 원금의 구성(예금 만기 + 적금 만기)을 말한다
 * - 같은 날의 다른 사건은 행이 따로다(키 `날짜:종류`). 행은 최신순으로 한 번에 모두 온다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { InstallmentTable } from "@/components/deposit/InstallmentTable";
import { ROWS } from "./support/installmentFixtures";

const header = () => screen.getAllByRole("columnheader").map((h) => {
  const copy = h.cloneNode(true) as HTMLElement;
  copy.querySelectorAll("span").forEach((s) => s.remove());
  return copy.textContent?.trim();
});

describe("적금 표", () => {
  it("열", () => {
    render(<InstallmentTable rows={ROWS} />);
    expect(header()).toEqual(["날짜", "구분", "회차", "적용 금리", "금액", "이자(세전)", "이자 소득세", "세후 이자", "적금 평가",
      "예금 평가", "평가액", "투자 수익", "수익률"]);
  });

  it("구분은 글자이고 같은 날의 사건은 행이 따로다", () => {
    render(<InstallmentTable rows={ROWS} />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((r) => r.getAttribute("data-kind"))).toEqual([
      "installment", "deposit_join", "deposit_maturity", "installment_maturity", "month", "installment"]);
    expect(rows.map((r) => r.querySelectorAll("td")[1].textContent)).toEqual([
      "납입", "예금 가입", "예금 만기", "적금 만기", "월", "납입"]);
  });

  it("납입 행은 회차와 그 달 금리다", () => {
    render(<InstallmentTable rows={ROWS} />);
    const cells = screen.getAllByRole("row")[1].querySelectorAll("td");
    expect(cells[2]).toHaveTextContent("1/12");
    expect(cells[3]).toHaveTextContent("1.82% (18-01)");
    expect(cells[4]).toHaveTextContent("1,000,000");
  });

  it("만기 행은 이자·세금·세후 이자이고 월 행은 금리·금액이 비어 있다", () => {
    render(<InstallmentTable rows={ROWS} />);
    const rows = screen.getAllByRole("row").slice(1);
    const maturity = rows[2].querySelectorAll("td");
    expect([maturity[5].textContent, maturity[6].textContent, maturity[7].textContent]).toEqual([
      "385,559", "59,376", "326,183"]);
    const month = rows[4].querySelectorAll("td");
    expect([month[2].textContent, month[3].textContent, month[4].textContent]).toEqual(["", "", ""]);
    expect(month[10]).toHaveTextContent("36,764,700");
  });

  it("예금 가입 행의 금액이 구성을 말한다", () => {
    render(<InstallmentTable rows={ROWS} />);
    expect(screen.getByTitle("원금 = 예금 만기 ₩24,728,664 + 적금 만기 ₩12,082,485")).toHaveTextContent("36,811,149");
  });

  it("잠정이면 구분에 ·잠정, 금리에 대신 쓴 달이다", () => {
    render(<InstallmentTable rows={[{ ...ROWS[0], provisional: true, rate: "3.46", rateMonth: "2026-08" }]} />);
    const cells = screen.getAllByRole("row")[1].querySelectorAll("td");
    expect(cells[1]).toHaveTextContent("납입·잠정");
    expect(cells[3]).toHaveTextContent("3.46% (26-08 대신)");
  });
});
