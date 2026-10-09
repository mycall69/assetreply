/**
 * 최종 지표 막대 (013 T053) — FR-015, SC-005, research R13-12, ui-wireframes F7.
 *
 * 수익률 묶음과 투자 수익 묶음이다. 글자 값은 표와 같은 형식 함수의 출력이다(서버 문자열). 값이 없으면 막대 없이 "—", 음수는 기준선
 * 왼쪽, 차례는 받은 차례(표의 지금 정렬)다. 잠정 입력을 쓴 대상은 이름 곁에 ⏳다(원칙 V).
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CompareMetricBars, type MetricItem } from "@/components/compare/CompareMetricBars";

const ITEMS: MetricItem[] = [
  { key: "a", name: "XLK", returnRate: "20.455734", profit: "409114677", provisional: false },
  { key: "b", name: "삼성전자", returnRate: "-0.125", profit: "-1250000", provisional: false },
  { key: "c", name: "시중은행", returnRate: null, profit: null, provisional: true },
];

const group = (name: string) => screen.getByRole("group", { name });
const rows = (name: string) => within(group(name)).getAllByRole("listitem");

describe("CompareMetricBars", () => {
  it("수익률과 투자 수익 두 묶음이고 차례는 받은 차례다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    expect(rows("수익률").map((r) => r.textContent)).toEqual([
      expect.stringContaining("XLK"), expect.stringContaining("삼성전자"), expect.stringContaining("시중은행")]);
    expect(rows("투자 수익")).toHaveLength(3);
  });

  it("글자 값은 표와 같은 형식이다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    // 013 승인 2026-10-09 — 반복 2026-10-09c(FR-021): 백분율의 정수부를 세 자리마다 쉼표로 끊는다.
    expect(rows("수익률")[0]).toHaveTextContent("+2,045.57%");
    expect(rows("투자 수익")[0]).toHaveTextContent("₩409,114,677");
    expect(rows("투자 수익")[1]).toHaveTextContent("-₩1,250,000");
  });

  it("값이 없으면 막대 없이 —다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    const row = rows("수익률")[2];
    expect(row).toHaveTextContent("—");
    expect(within(row).queryByTestId("metric-bar")).toBeNull();
  });

  it("음수 막대는 기준선 왼쪽이다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    expect(within(rows("수익률")[1]).getByTestId("metric-bar")).toHaveAttribute("data-sign", "negative");
    expect(within(rows("수익률")[0]).getByTestId("metric-bar")).toHaveAttribute("data-sign", "positive");
  });

  it("가장 큰 값의 막대가 가장 길다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    const width = (i: number) => within(rows("수익률")[i]).getByTestId("metric-bar").style.width;
    expect(width(0)).toBe("100%");
    expect(Number.parseFloat(width(1))).toBeLessThan(100);
  });

  it("잠정 대상은 이름 곁에 ⏳다", () => {
    render(<CompareMetricBars items={ITEMS} />);
    expect(rows("수익률")[2]).toHaveTextContent("⏳");
    expect(rows("수익률")[0]).not.toHaveTextContent("⏳");
  });
});
