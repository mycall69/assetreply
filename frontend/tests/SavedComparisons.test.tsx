/**
 * 저장한 비교 칸 (013 T065) — FR-016~FR-019, ui-wireframes F9.
 *
 * 줄마다 이름, "자산군 · 대상 이름들"(셋 넘으면 "외 N개"), 시작일·방식, 저장 시각(한국 시간). 불러오기·삭제 단추는 이름을 밝힌다. 안내는 보관 기간 대신
 * "지울 때까지 남습니다"다(명확화 3). 실패는 알림이다 — 목록 받기 실패는 다시 시도, 저장·삭제 실패는 문구(FR-019).
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SavedComparisons } from "@/components/compare/SavedComparisons";
import type { CompareCondition } from "@/lib/compareCondition";
import type { SavedComparison } from "@/lib/types";
import { AAPL_T, HYNIX_T, SAMSUNG_T, XLK_T } from "./support/compareFixtures";

const stock = (over: Partial<CompareCondition> = {}): CompareCondition => ({
  v: 1, asset: "stock", method: "lump_sum", frequency: null, start: "2020-01-02", amount: "10000000",
  principalCurrency: "KRW", reinvest: true, targets: [SAMSUNG_T, HYNIX_T, XLK_T], ...over,
});

const entry = (id: number, name: string, condition: CompareCondition, savedAt = "2026-10-08T03:21:07Z"): SavedComparison => ({
  id, name, asset: condition.asset, condition, savedAt,
});

function draw(props: Partial<Parameters<typeof SavedComparisons>[0]> = {}) {
  const handlers = { onLoad: vi.fn(), onRemove: vi.fn(), onRetry: vi.fn() };
  render(<SavedComparisons entries={[]} loading={false} loadError={null} saveError={null} removeError={null}
    {...handlers} {...props} />);
  return handlers;
}

describe("저장한 비교", () => {
  it("줄: 이름, 자산군 · 대상 이름들, 시작일 · 방식, 저장 시각(한국 시간)", () => {
    draw({ entries: [entry(1, "주식 3개 · 2020-01-02 · 일시금", stock())] });
    const row = screen.getByTestId("saved-comparison");
    expect(row).toHaveTextContent("주식 3개 · 2020-01-02 · 일시금");
    expect(row).toHaveTextContent("주식 · 삼성전자, SK하이닉스, Technology Select Sector SPDR Fund");
    expect(row).toHaveTextContent("2020-01-02 · 일시금");
    expect(row).toHaveTextContent("10-08 12:21 저장");
  });

  it("대상이 셋을 넘으면 '외 N개'다", () => {
    const five = [SAMSUNG_T, HYNIX_T, XLK_T, AAPL_T, { ...AAPL_T, symbol: "MSFT", name: "Microsoft" }];
    draw({ entries: [entry(1, "다섯", stock({ targets: five }))] });
    expect(screen.getByTestId("saved-comparison"))
      .toHaveTextContent("주식 · 삼성전자, SK하이닉스, Technology Select Sector SPDR Fund 외 2개");
  });

  it("적립식은 주기를 함께 보인다", () => {
    draw({ entries: [entry(1, "적립", stock({ method: "recurring", frequency: "monthly" }))] });
    expect(screen.getByTestId("saved-comparison")).toHaveTextContent("2020-01-02 · 적립식 매달");
  });

  it("불러오기·삭제 단추는 이름을 밝히고 id를 넘긴다", () => {
    const h = draw({ entries: [entry(7, "가", stock()), entry(3, "나", stock())] });
    fireEvent.click(screen.getByRole("button", { name: "나 불러오기" }));
    expect(h.onLoad).toHaveBeenCalledWith(3);
    fireEvent.click(screen.getByRole("button", { name: "가 삭제" }));
    expect(h.onRemove).toHaveBeenCalledWith(7);
  });

  it("받은 차례 그대로다", () => {
    draw({ entries: [entry(9, "나중", stock()), entry(2, "먼저", stock())] });
    expect(screen.getAllByTestId("saved-comparison").map((r) => within(r).getByTestId("saved-name").textContent))
      .toEqual(["나중", "먼저"]);
  });

  it("안내는 지울 때까지 남는다는 것이고 보관 기간 문장이 없다", () => {
    draw();
    const notice = screen.getByTestId("saved-notice");
    expect(notice).toHaveTextContent("이 기기의 로컬 DB에 저장됩니다. 지울 때까지 남습니다.");
    expect(notice.textContent).not.toMatch(/일이 지나면|설정에서/);
  });

  it("빈 목록 문구", () => {
    draw();
    expect(screen.getByText("아직 저장한 비교가 없습니다.")).toBeInTheDocument();
    expect(screen.queryByText("아직 실행한 시뮬레이션이 없습니다.")).toBeNull();
  });

  it("목록 받기 실패는 알림과 다시 시도이고 빈 문구가 없다", () => {
    const h = draw({ loadError: "저장한 비교를 받지 못했습니다" });
    expect(screen.getByRole("alert")).toHaveTextContent("저장한 비교를 받지 못했습니다");
    expect(screen.queryByText("아직 저장한 비교가 없습니다.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(h.onRetry).toHaveBeenCalled();
  });

  it("저장·삭제 실패는 알림 문구다", () => {
    draw({ entries: [entry(1, "가", stock())], saveError: "저장하지 못했습니다 — 서버 오류", removeError: "지우지 못했습니다 — 서버 오류" });
    const alerts = screen.getAllByRole("alert").map((a) => a.textContent);
    expect(alerts).toContain("저장하지 못했습니다 — 서버 오류");
    expect(alerts).toContain("지우지 못했습니다 — 서버 오류");
    expect(screen.getByTestId("saved-comparison")).toBeInTheDocument();
  });
});
