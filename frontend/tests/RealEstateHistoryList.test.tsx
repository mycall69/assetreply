/**
 * 부동산 최근 시뮬레이션 (T049) — 009 FR-032, ui-wireframes E7. 008 `DepositHistory`와 같은 줄이다 — 고르기·다시 실행·삭제.
 *
 * - 한 줄은 **단지·평형·매입일·매입가**다. 매입가는 직접 넣었으면 금액, 아니면 "그 달 시세" — 시세로 산 조건을 금액 없이 두면
 *   매입가를 잃은 것처럼 보인다
 * - **수익률을 줄에 적지 않는다** — 결과는 거래·세법·비율이 바뀌면 달라진다(005 R5-9)
 * - 보관 위치와 다른 자산군 이력과 따로라는 사실을 알린다
 * - 버튼·고르기의 이름은 단지·평형·매입일이다 — 같은 단지·평형을 다른 날 산 줄이 여럿일 수 있다
 *
 * ## 이 테스트가 전제하는 모듈 (T050이 따른다)
 *
 * `@/components/realestate/RealEstateHistory` — `export function RealEstateHistory(props)`, `DepositHistory`와 같은 속성:
 * `entries: RealEstateHistoryEntry[]`, `selected: string[]`, `comparing: boolean`, `saveError: string | null`,
 * `onToggle(id)`, `onRemove(id)`, `onCompare()`, `onRerun(id)`. 줄은 `data-testid="history-row"`, 안내는 `data-testid="history-notice"`.
 * 이름은 `"헬리오시티 20평대 2021-03-15 다시 실행"`·`"… 이력 삭제"`·`"… 비교 대상으로 선택"`
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RealEstateHistory } from "@/components/realestate/RealEstateHistory";
import type { RealEstateHistoryEntry } from "@/lib/types";

const ENTRIES: RealEstateHistoryEntry[] = [
  { id: "a", complexId: 12, complexName: "헬리오시티", umd: "1171010700", area: "30k", areaLabel: "30평대(국평)",
    buyDate: "2021-03-15", buyPrice: null, savedAt: "2026-10-05T00:00:00Z" },
  { id: "b", complexId: 12, complexName: "헬리오시티", umd: "1171010700", area: "20", areaLabel: "20평대",
    buyDate: "2021-03-15", buyPrice: "1500000000", savedAt: "2026-10-05T00:00:00Z" },
];

function renderHistory(selected: string[] = [], over: Partial<{ entries: RealEstateHistoryEntry[];
  saveError: string | null; comparing: boolean }> = {}) {
  const props = { onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn() };
  render(<RealEstateHistory entries={over.entries ?? ENTRIES} selected={selected} comparing={over.comparing ?? false}
    saveError={over.saveError ?? null} {...props} />);
  return props;
}

const rows = () => screen.getAllByTestId("history-row");

describe("부동산 이력", () => {
  it("한 줄은 단지·평형·매입일이고 수익률이 없다", () => {
    renderHistory();
    expect(rows()).toHaveLength(2);
    const text = rows()[0].textContent ?? "";
    expect(text).toContain("헬리오시티 30평대(국평)");
    expect(text).toContain("2021-03-15");
    expect(text).not.toMatch(/%/);
  });

  it("매입가 칸 — 그 달 시세로 샀으면 그 사실, 직접 넣었으면 금액", () => {
    renderHistory();
    expect(rows()[0].textContent).toContain("그 달 시세");
    expect(rows()[1].textContent).toContain("1,500,000,000원");
    expect(rows()[1].textContent).not.toContain("그 달 시세");
  });

  it("보관 위치와 다른 자산군 이력과 따로라는 사실을 알린다", () => {
    renderHistory();
    const notice = screen.getByTestId("history-notice").textContent ?? "";
    expect(notice).toContain("이 브라우저에만 저장됩니다");
    expect(notice).toContain("다른 자산군 이력과 따로입니다");
  });

  it("다시 실행·삭제·고르기 — 이름에 단지·평형·매입일", async () => {
    const props = renderHistory();
    const row = rows()[1];
    await userEvent.click(within(row).getByRole("button", { name: "헬리오시티 20평대 2021-03-15 다시 실행" }));
    await userEvent.click(within(row).getByRole("button", { name: "헬리오시티 20평대 2021-03-15 이력 삭제" }));
    await userEvent.click(within(row).getByRole("checkbox", { name: "헬리오시티 20평대 2021-03-15 비교 대상으로 선택" }));
    expect(props.onRerun).toHaveBeenCalledWith("b");
    expect(props.onRemove).toHaveBeenCalledWith("b");
    expect(props.onToggle).toHaveBeenCalledWith("b");
  });

  it("고른 줄은 체크되어 있다", () => {
    renderHistory(["a"]);
    expect(within(rows()[0]).getByRole("checkbox")).toBeChecked();
    expect(within(rows()[1]).getByRole("checkbox")).not.toBeChecked();
  });

  it("둘 이상 골라야 비교할 수 있다", () => {
    renderHistory(["a"]);
    expect(screen.getByRole("button", { name: "선택 항목 비교" })).toBeDisabled();
  });

  it("둘을 고르면 비교한다", async () => {
    const props = renderHistory(["a", "b"]);
    await userEvent.click(screen.getByRole("button", { name: "선택 항목 비교" }));
    expect(props.onCompare).toHaveBeenCalled();
  });

  it("저장하지 못했으면 그 사실을 알린다", () => {
    renderHistory([], { saveError: "이력을 저장하지 못했습니다." });
    expect(screen.getByRole("alert").textContent).toContain("이력을 저장하지 못했습니다");
  });

  it("이력이 없으면 그 사실을 말한다", () => {
    renderHistory([], { entries: [] });
    expect(screen.queryAllByTestId("history-row")).toHaveLength(0);
    expect(screen.getByText(/아직 실행한 시뮬레이션이 없습니다/)).toBeInTheDocument();
  });
});
