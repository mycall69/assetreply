/**
 * 엔터로 맨 위 결과 고르기 (T129) — 006 FR-056, SC-022, ui-wireframes W2. 반복 2026-10-03 #3.
 *
 * 방향키로 고른 항목 없이 엔터를 치면 아무 일도 없었다 — 사용자는 검색이 멈춘 것으로 읽는다. 맨 위 결과(국내·미국 첫 줄,
 * 없으면 일본 첫 줄)를 고른다. 방향키로 고른 항목이 있으면 그 항목이다.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import {
  SAMSUNG,
  SAMSUNG_PREF,
  TOYOTA,
  external,
  local,
  routeGet,
} from "./support/stockSearchFixtures";

beforeEach(() => {
  vi.restoreAllMocks();
});

async function search(text: string) {
  const onSelect = vi.fn();
  render(<StockSearch value={null} onSelect={onSelect} />);
  await userEvent.type(screen.getByRole("searchbox"), text);
  return onSelect;
}

describe("엔터", () => {
  it("고른 항목이 없으면 국내·미국 첫 결과를 고른다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, SAMSUNG_PREF])) });
    const onSelect = await search("삼성");
    await screen.findByRole("option", { name: /삼성전자우/ });
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(
      { source: "listing", listingId: SAMSUNG.listingId, preview: SAMSUNG });
  });

  it("국내·미국이 비면 일본 첫 결과를 고른다", async () => {
    routeGet({
      local: () => Promise.resolve(local([])),
      external: () => Promise.resolve(external([TOYOTA])),
    });
    const onSelect = await search("토요타");
    await screen.findByRole("option", { name: /Toyota/ });
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith({ source: "external", result: TOYOTA });
  });

  it("결과가 없으면 아무 일도 하지 않는다", async () => {
    routeGet({ local: () => Promise.resolve(local([])) });
    const onSelect = await search("없는종목");
    await screen.findByText(/일본 종목을 찾지 못했습니다/);
    await userEvent.keyboard("{Enter}");
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("방향키로 고른 항목이 있으면 그 항목이다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, SAMSUNG_PREF])) });
    const onSelect = await search("삼성");
    await screen.findByRole("option", { name: /삼성전자우/ });
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith(
      { source: "listing", listingId: SAMSUNG_PREF.listingId, preview: SAMSUNG_PREF });
  });
});

/**
 * 한글 조합 중 엔터 (T146) — 버그 `search-enter-ime`(.specify/bugs/search-enter-ime/), 006 FR-056.
 *
 * 한글 입력기는 마지막 글자를 조합 중인 채로 엔터를 받아 **조합 확정**에 쓴다. 그 keydown도 `key: "Enter"`로 오는데
 * (조합 중·keyCode 229), 처리기가 거기서 고르고 칸을 비우면 입력기가 조합 중이던 글자를 빈 칸에 확정해 넣는다 — "삼성전자" 뒤
 * 엔터가 칸을 `자`로 만들고 `자` 검색 결과를 열었다(2026-10-03 사용자 보고, Chrome 154 재현). 위 테스트들은 `userEvent.type`으로
 * 조합 없이 글자를 넣어 이 경로를 지나지 않았다.
 */
describe("한글 조합 중 엔터", () => {
  async function composing() {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, SAMSUNG_PREF])) });
    const onSelect = vi.fn();
    render(<StockSearch value={null} onSelect={onSelect} />);
    const box = screen.getByRole("searchbox");
    // "삼성전"은 확정, "자"는 조합 중 — 조합 중에도 입력 이벤트가 와서 칸 값은 "삼성전자"다.
    fireEvent.change(box, { target: { value: "삼성전" } });
    fireEvent.compositionStart(box);
    fireEvent.change(box, { target: { value: "삼성전자" } });
    await screen.findByRole("option", { name: /삼성전자우/ });
    return { box, onSelect };
  }

  /**
   * 입력기가 조합을 확정한다. **칸이 그 사이 비었으면 확정한 글자가 빈 칸에 들어간다** — Chrome 기록
   * (`keydown Enter/229 composing value=삼성전자` → `input data=자 value=자`). 비지 않았으면 칸 값은 그대로다.
   */
  function commit(box: HTMLElement, syllable: string) {
    fireEvent.compositionEnd(box, { data: syllable });
    if ((box as HTMLInputElement).value === "") {
      fireEvent.change(box, { target: { value: syllable } });
    }
  }

  it("조합 중 엔터에서는 고르지 않고 칸도 그대로다", async () => {
    const { box, onSelect } = await composing();
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229, isComposing: true });
    expect(onSelect).not.toHaveBeenCalled();
    expect(box).toHaveValue("삼성전자");
  });

  it("조합이 확정된 뒤의 엔터에서 맨 위 결과를 한 번 고르고 칸이 빈다", async () => {
    const { box, onSelect } = await composing();
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229, isComposing: true });
    commit(box, "자");
    fireEvent.keyDown(box, { key: "Enter", keyCode: 13 });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(
      { source: "listing", listingId: SAMSUNG.listingId, preview: SAMSUNG });
    // 고친 전에는 여기서 칸이 "자"였다.
    expect(box).toHaveValue("");
  });

  it("Safari 순서 — 조합 확정 뒤 오는 keyCode 229 엔터도 고르지 않는다", async () => {
    // Safari는 compositionend를 keydown보다 먼저 보내, 그 keydown은 isComposing이 거짓이고 keyCode만 229다.
    const { box, onSelect } = await composing();
    fireEvent.compositionEnd(box, { data: "자" });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229, isComposing: false });
    expect(onSelect).not.toHaveBeenCalled();
    expect(box).toHaveValue("삼성전자");
  });

  it("조합 중 방향키는 항목을 옮기지 않는다", async () => {
    // 조합 중 방향키는 입력기가 쓴다. 옮기면 확정 뒤 엔터가 사용자가 보지 않은 항목을 고른다.
    const { box, onSelect } = await composing();
    fireEvent.keyDown(box, { key: "ArrowDown", keyCode: 229, isComposing: true });
    fireEvent.keyDown(box, { key: "ArrowDown", keyCode: 229, isComposing: true });
    commit(box, "자");
    fireEvent.keyDown(box, { key: "Enter", keyCode: 13 });
    expect(onSelect).toHaveBeenCalledWith(
      { source: "listing", listingId: SAMSUNG.listingId, preview: SAMSUNG });
  });
});
