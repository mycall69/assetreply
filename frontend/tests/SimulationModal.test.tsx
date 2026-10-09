/**
 * 투자 시뮬레이션 모달 (013 반복 2026-10-09b T097) — FR-011b, ui-wireframes F10, research R13-19.
 *
 * - 일곱 방식마다 메뉴 화면과 같은 부품 — 투자 결과 패널·성과 추이·일자별(부동산 월별) 투자 성과. 머리에 이름·자산군·방식·그 줄의 조건·기준일
 * - `role="dialog"`·`aria-modal`, ×·Esc·바깥 누름으로 닫힘, 포커스 이동·복귀·가두기, 배경 스크롤 잠금
 * - 202·오류는 까닭과 다시 시도, `/series`만 실패하면 패널·표는 남는다
 * - 화면은 계산하지 않는다(새 파일에 숫자 변환이 없다 — `compareNoClientFinance`와 같은 검사)
 */
import { readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SimulationModal } from "@/components/compare/SimulationModal";
import { COLLECTING_REASON, useCompareDetailStore, type DetailState } from "@/stores/compareDetailStore";
import { CASES, SERIES, STOCK_LUMP } from "./support/compareDetailFixtures";

vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const opened = (c: (typeof CASES)[number], over: Partial<DetailState> = {}) => act(() => {
  useCompareDetailStore.setState({
    open: { key: c.label, name: c.name, href: null, condition: c.condition, target: c.target },
    status: "ok", reason: null, menu: c.menu, series: SERIES, seriesError: null, ...over,
  });
});

beforeEach(() => {
  vi.restoreAllMocks();
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
  document.body.style.overflow = "";
});

describe("내용 — 메뉴와 같은 부품", () => {
  it.each(CASES.map((c) => [c.label, c]))("%s", (_label, c) => {
    render(<SimulationModal />);
    opened(c);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName(new RegExp(c.name.split(" ")[0]));
    expect(within(dialog).getByTestId("simulation-modal-board")).toHaveTextContent(c.boardText);
    expect(within(dialog).getByTestId("simulation-modal-chart")).toHaveTextContent("성과 추이");
    expect(within(dialog).getByTestId("simulation-modal-table")).toHaveTextContent(c.tableText);
    expect(within(dialog).getByTestId("simulation-modal-condition"))
      .toHaveTextContent(`기준일 ${(c.menu.summary as { asOf: string }).asOf}`);
  });

  it("머리는 자산군·방식과 그 줄의 조건이다", () => {
    render(<SimulationModal />);
    opened(CASES[1]);
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("투자 시뮬레이션 · 주식 · 적립식 매주");
    expect(screen.getByTestId("simulation-modal-condition")).toHaveTextContent("시작일 2024-01-15 · 매주 ₩500,000 · 배당 재투자");
  });

  it("부동산은 매입일, 월별 표 제목이다", () => {
    render(<SimulationModal />);
    opened(CASES[6]);
    expect(screen.getByTestId("simulation-modal-condition")).toHaveTextContent("매입일 2021-03-15");
    expect(screen.getByTestId("simulation-modal-table")).toHaveTextContent("월별 투자 성과");
  });

  it("주식 일자별 표는 일·주·월 단추와 이어 받기(아래로 스크롤 — 메뉴와 같다)가 모달 스토어를 부른다", () => {
    const setPeriod = vi.fn(async () => undefined);
    const loadMore = vi.fn(async () => undefined);
    render(<SimulationModal />);
    opened(CASES[0], { setPeriod, loadMore });
    const table = screen.getByTestId("simulation-modal-table");
    fireEvent.click(within(table).getByRole("tab", { name: /주/ }));
    expect(setPeriod).toHaveBeenCalledWith("weekly");
    // 더 있으면 메뉴 표처럼 관찰 지점이 있고, 이어 받기가 실패하면 "다시 시도"가 모달 스토어의 이어 받기를 부른다.
    expect(within(table).getByTestId("scroll-sentinel")).toBeInTheDocument();
    opened(CASES[0], { setPeriod, loadMore, loadMoreError: "이어서 불러오지 못했습니다." });
    fireEvent.click(within(screen.getByTestId("simulation-modal-table")).getByRole("button", { name: "다시 시도" }));
    expect(loadMore).toHaveBeenCalled();
  });
});

describe("닫기·포커스·스크롤", () => {
  it("×·Esc·바깥 누름으로 닫힌다", () => {
    render(<SimulationModal />);
    opened(CASES[0]);
    fireEvent.click(screen.getByRole("button", { name: "투자 시뮬레이션 닫기" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    opened(CASES[0]);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    opened(CASES[0]);
    fireEvent.mouseDown(screen.getByRole("dialog").parentElement as HTMLElement);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("안을 눌러도 닫히지 않는다", () => {
    render(<SimulationModal />);
    opened(CASES[0]);
    fireEvent.mouseDown(screen.getByTestId("simulation-modal-board"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("열면 닫기 단추로, 닫으면 연 단추로 포커스가 간다", () => {
    render(<><button type="button">삼성전자 투자 시뮬레이션</button><SimulationModal /></>);
    const trigger = screen.getByRole("button", { name: "삼성전자 투자 시뮬레이션" });
    trigger.focus();
    opened(CASES[0]);
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "투자 시뮬레이션 닫기" }));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.activeElement).toBe(trigger);
  });

  it("Tab·Shift+Tab은 모달 안에서 돈다", () => {
    render(<><button type="button">뒤의 단추</button><SimulationModal /></>);
    opened(CASES[0]);
    const dialog = screen.getByRole("dialog");
    const items = [...dialog.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input, select, [tabindex]:not([tabindex='-1'])")];
    const first = items[0];
    const last = items[items.length - 1];
    last.focus();
    fireEvent.keyDown(document, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    first.focus();
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("열린 동안 배경 스크롤을 잠그고 닫으면 되돌린다", () => {
    document.body.style.overflow = "auto";
    render(<SimulationModal />);
    opened(CASES[0]);
    expect(document.body.style.overflow).toBe("hidden");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(document.body.style.overflow).toBe("auto");
  });
});

describe("실패", () => {
  it("202는 까닭과 다시 시도다", () => {
    const retry = vi.fn(async () => undefined);
    render(<SimulationModal />);
    opened(CASES[0], { status: "collecting", reason: COLLECTING_REASON, menu: null, retry });
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(COLLECTING_REASON);
    fireEvent.click(within(alert).getByRole("button", { name: "다시 시도" }));
    expect(retry).toHaveBeenCalled();
    expect(screen.queryByTestId("simulation-modal-board")).toBeNull();
  });

  it("오류는 까닭이다", () => {
    render(<SimulationModal />);
    opened(CASES[0], { status: "failed", reason: "알 수 없는 종목입니다", menu: null });
    expect(screen.getByRole("alert")).toHaveTextContent("알 수 없는 종목입니다");
  });

  it("/series만 실패하면 패널·표는 남고 차트 자리에 까닭이다", () => {
    render(<SimulationModal />);
    opened(CASES[0], { series: null, seriesError: "성과 추이를 불러오지 못했습니다." });
    expect(within(screen.getByTestId("simulation-modal-chart")).getByRole("alert"))
      .toHaveTextContent("성과 추이를 불러오지 못했습니다.");
    expect(screen.getByTestId("simulation-modal-board")).toBeInTheDocument();
    expect(screen.getByTestId("simulation-modal-table")).toHaveTextContent("2021-08-31");
  });

  it("닫혀 있으면 아무것도 그리지 않는다", () => {
    render(<SimulationModal />);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(STOCK_LUMP.rows).toHaveLength(1);
  });
});

describe("계산하지 않는다", () => {
  it("새 파일에 숫자 변환이 없다", () => {
    const src = join(process.cwd(), "src");
    const files = ["stores/compareDetailStore.ts", "components/compare/SimulationModal.tsx", "lib/boardNotes.ts",
      ...readdirSync(join(src, "components/compare/detail")).map((f) => `components/compare/detail/${f}`)];
    const strip = (s: string) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/[^\n]*/g, "");
    const offenders = files.filter((rel) => /\b(Number|parseFloat|parseInt)\s*\(/.test(strip(readFileSync(join(src, rel), "utf-8"))));
    expect(offenders).toEqual([]);
  });
});
