/**
 * 엔터로 맨 위 결과 고르기 (T129) — 006 FR-056, SC-022, ui-wireframes W2. 반복 2026-10-03 #3.
 *
 * 방향키로 고른 항목 없이 엔터를 치면 아무 일도 없었다 — 사용자는 검색이 멈춘 것으로 읽는다. 맨 위 결과(국내·미국 첫 줄,
 * 없으면 일본 첫 줄)를 고른다. 방향키로 고른 항목이 있으면 그 항목이다.
 */
import { render, screen } from "@testing-library/react";
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
