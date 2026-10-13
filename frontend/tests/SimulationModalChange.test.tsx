/**
 * 투자 비교 투자 시뮬레이션 모달의 등락 열 (014 반복 2026-10-13b T222) — spec FR-047, SC-029, contracts D20.
 *
 * 모달은 메뉴와 같은 부품·같은 경로다(013 FR-011b) — 주식·가상자산 × 일시금·적립식 넷 모두 메뉴 표와 같은 열·같은 글자다. 메뉴만 고치고 모달을
 * 따로 두면 같은 조건의 표가 두 곳에서 다르다(FR-047 실패 양상).
 */
import { act, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SimulationModal } from "@/components/compare/SimulationModal";
import type { PriceChange } from "@/lib/types";
import { useCompareDetailStore } from "@/stores/compareDetailStore";
import { CASES, SERIES } from "./support/compareDetailFixtures";

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const up: PriceChange = { comparedTo: "2021-07-30", absolute: "500.000000", percent: "0.63", direction: "up", split: null };
const down: PriceChange = { comparedTo: "2021-07-30", absolute: "-120.000000", percent: "-0.15", direction: "down", split: null };

beforeEach(() => {
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
});

function open(label: string, rows: unknown[]) {
  const c = CASES.find((x) => x.label === label);
  if (c === undefined) throw new Error(label);
  act(() => {
    useCompareDetailStore.setState({
      open: { key: c.label, name: c.name, href: null, condition: c.condition, target: c.target },
      status: "ok", reason: null, menu: { ...c.menu, rows } as never, series: SERIES, seriesError: null,
    });
  });
  return c;
}

function cell(table: HTMLElement, name: string): string {
  const heads = within(table).getAllByRole("columnheader");
  const index = heads.findIndex((h) => (h.textContent ?? "").startsWith(name));
  expect(index, `열 없음: ${name}`).toBeGreaterThanOrEqual(0);
  const body = within(table).getAllByRole("row").filter((r) => within(r).queryAllByRole("cell").length > 0)[0];
  return within(body).getAllByRole("cell")[index].textContent ?? "";
}

describe("모달 표의 등락", () => {
  it.each(["주식 일시금", "주식 적립식"])("%s — 시작가·종가 묶음", (label) => {
    render(<SimulationModal />);
    open(label, [{ ...(c0(label).menu.rows[0] as object), openChange: up, closeChange: down }]);
    const table = screen.getByTestId("simulation-modal-table");
    expect(within(table).getByRole("columnheader", { name: "시작가 등락폭" })).toBeInTheDocument();
    expect(within(table).getByRole("columnheader", { name: "종가 등락률" })).toBeInTheDocument();
    expect(cell(table, "시작가 등락폭")).toBe("▲ 500.00");
    expect(cell(table, "시작가 등락률")).toBe("+0.63%");
    expect(cell(table, "종가 등락폭")).toBe("▼ 120.00");
    expect(cell(table, "종가 등락률")).toBe("-0.15%");
  });

  it.each(["가상자산 일시금", "가상자산 적립식"])("%s — 시가 묶음", (label) => {
    render(<SimulationModal />);
    open(label, [{ ...(c0(label).menu.rows[0] as object), openChange: up }]);
    const table = screen.getByTestId("simulation-modal-table");
    expect(within(table).getByRole("columnheader", { name: /^시가 등락폭/ })).toBeInTheDocument();
    expect(cell(table, "시가 등락폭")).toBe("▲ 500.00");
    expect(cell(table, "시가 등락률")).toBe("+0.63%");
    expect(within(table).queryByRole("columnheader", { name: /종가 등락/ })).toBeNull();
  });
});

function c0(label: string) {
  const c = CASES.find((x) => x.label === label);
  if (c === undefined) throw new Error(label);
  return c;
}
