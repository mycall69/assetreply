/**
 * 투자 비교 화면 (013 T020) — FR-001~FR-014, SC-008, ui-wireframes F1~F5·F8.
 *
 * 자산군을 고르고 메뉴와 같은 부품으로 대상을 더해 공통 조건으로 실행한다. 막히면 결과 대신 막힘 칸(이름·까닭·제안)이고, 계산된 대상부터
 * 보이며, 결과를 본 뒤 조건을 바꾸면 흐린다. 비교는 이력을 쓰지 않는다.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import { apiClient } from "@/lib/apiClient";
import type { StockProgressHandlers } from "@/lib/stockProgressStream";
import { useCompareStore } from "@/stores/compareStore";
import { useCompareRealEstatePicker } from "@/stores/compareRealEstatePicker";
import {
  HYNIX_T,
  SAMSUNG_T,
  XLK_T,
  apiError,
  collectingStock,
  ok,
} from "./support/compareFixtures";
import { historyStub } from "./support/historyStub";
import { SAMSUNG, local } from "./support/stockSearchFixtures";

const streams = vi.hoisted(() => ({ stock: [] as { handlers: StockProgressHandlers; active: boolean }[] }));
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: (_jobId: number, handlers: StockProgressHandlers) => {
    const sub = { handlers, active: true };
    streams.stock.push(sub);
    return () => {
      sub.active = false;
    };
  },
}));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
vi.mock("@/lib/realEstateProgressStream", () => ({ subscribeRealEstateProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));
// 실제 차트는 jsdom에서 그릴 수 없다(`matchMedia` 없음 — 처리되지 않은 오류로 실행이 실패한다).
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

type Answer = (path: string) => unknown;

function route(answer: Answer) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    if (path.startsWith("/api/stocks/search/external")) return Promise.resolve({ query: "", results: [] });
    if (path.startsWith("/api/stocks/search")) return Promise.resolve(local([SAMSUNG]));
    const result = answer(path);
    if (result === undefined) return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
    if (result instanceof Promise) return result;
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  }) as typeof apiClient.get);
}

beforeEach(() => {
  vi.restoreAllMocks();
  streams.stock.length = 0;
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02" });
  useCompareRealEstatePicker.getState().dispose();
  useCompareRealEstatePicker.setState(useCompareRealEstatePicker.getInitialState(), true);
});

const runButton = () => screen.getByRole("button", { name: "비교 실행" });

describe("화면", () => {
  it("제목과 자산군 라디오 넷이다 — 처음은 주식", () => {
    route(() => undefined);
    render(<ComparePage />);
    expect(screen.getByRole("heading", { name: "투자 비교" })).toBeInTheDocument();
    const group = screen.getByRole("radiogroup", { name: "자산군" });
    expect(within(group).getAllByRole("radio").map((r) => r.getAttribute("value")))
      .toEqual(["stock", "crypto", "deposit", "realestate"]);
    expect(within(group).getByRole("radio", { name: "주식" })).toBeChecked();
  });

  it("주식 검색으로 고르면 등록한 종목이 대상 칩으로 쌓인다", async () => {
    route(() => undefined);
    vi.spyOn(apiClient, "post").mockResolvedValue({ ...SAMSUNG_T, listedOn: "1975-06-11" });
    render(<ComparePage />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    await userEvent.click(await screen.findByRole("option", { name: /삼성전자/ }));
    expect(await screen.findByRole("button", { name: "삼성전자 빼기" })).toBeInTheDocument();
    expect(screen.getByText(/1\/10/)).toBeInTheDocument();
  });

  it("대상이 2개보다 적으면 실행할 수 없다", () => {
    route(() => undefined);
    useCompareStore.getState().addTarget(SAMSUNG_T);
    render(<ComparePage />);
    expect(runButton()).toBeDisabled();
    expect(screen.getByText(/2개 이상이 필요합니다/)).toBeInTheDocument();
  });

  it("칩의 빼기 단추로 뺀다", () => {
    route(() => undefined);
    useCompareStore.getState().addTarget(SAMSUNG_T);
    useCompareStore.getState().addTarget(HYNIX_T);
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스 빼기" }));
    expect(screen.queryByRole("button", { name: "SK하이닉스 빼기" })).toBeNull();
  });

  it("11번째는 더하지 않고 알린다", () => {
    route(() => undefined);
    for (let i = 0; i < 10; i += 1) useCompareStore.getState().addTarget({ ...SAMSUNG_T, symbol: `00000${i}.KS`, name: `종목${i}` });
    useCompareStore.getState().addTarget({ ...SAMSUNG_T, symbol: "999999.KS" });
    render(<ComparePage />);
    expect(screen.getByRole("alert")).toHaveTextContent("최대 10개");
  });
});

describe("실행", () => {
  beforeEach(() => {
    useCompareStore.getState().addTarget(SAMSUNG_T);
    useCompareStore.getState().addTarget(XLK_T);
  });

  it("대상마다 한 줄의 비교 표다", async () => {
    route((path) => ok(path.includes("XLK") ? XLK_T : SAMSUNG_T));
    render(<ComparePage />);
    fireEvent.click(runButton());
    const table = await screen.findByRole("table", { name: "비교 표" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual([
      expect.stringContaining("삼성전자"), expect.stringContaining("Technology Select Sector SPDR Fund")]);
    expect(screen.getAllByText(/₩409,114,677/)).toHaveLength(2);
  });

  it("막히면 결과 대신 막힘 칸이고 제안을 누르면 시작일만 옮긴다", async () => {
    const get = route((path) => (path.includes("XLK")
      ? apiError(400, "before_listing", { startableFrom: "2021-11-29", basis: "listing" }) : ok(SAMSUNG_T)));
    render(<ComparePage />);
    fireEvent.click(runButton());
    const panel = await screen.findByRole("alert", { name: "비교할 수 없습니다" });
    expect(panel).toHaveTextContent("Technology Select Sector SPDR Fund");
    expect(panel).toHaveTextContent("상장 전");
    expect(panel).toHaveTextContent("2021-11-29");
    expect(screen.queryByRole("table", { name: "비교 표" })).toBeNull();
    const calls = get.mock.calls.length;
    fireEvent.click(within(panel).getByRole("button", { name: "시작일 옮기기" }));
    expect(useCompareStore.getState().start).toBe("2021-11-29");
    expect(get.mock.calls.length).toBe(calls);
  });

  it("받아 둔 대상부터 보이고 수집 중인 대상은 끝나면 채워진다", async () => {
    let xlk = 0;
    route((path) => (path.includes("XLK") ? ((xlk += 1) === 1 ? collectingStock(41) : ok(XLK_T)) : ok(SAMSUNG_T)));
    render(<ComparePage />);
    fireEvent.click(runButton());
    expect(await screen.findByText(/수집 중 ·/)).toBeInTheDocument();
    expect(screen.getAllByText(/₩409,114,677/)).toHaveLength(1);
    streams.stock[0].handlers.onCompleted();
    await waitFor(() => expect(screen.getAllByText(/₩409,114,677/)).toHaveLength(2));
    expect(screen.queryByText(/수집 중 ·/)).toBeNull();
  });

  it("결과를 본 뒤 시작일을 바꾸면 흐리고, 되돌리면 풀린다", async () => {
    route(() => ok(SAMSUNG_T));
    render(<ComparePage />);
    fireEvent.click(runButton());
    await screen.findByRole("table", { name: "비교 표" });
    useCompareStore.getState().setStart("2021-01-04");
    expect(await screen.findByRole("status", { name: "조건이 바뀜" })).toHaveTextContent("다시 실행");
    useCompareStore.getState().setStart("2020-01-02");
    await waitFor(() => expect(screen.queryByRole("status", { name: "조건이 바뀜" })).toBeNull());
  });

  it("비교는 이력을 쓰지 않는다", async () => {
    route(() => ok(SAMSUNG_T));
    render(<ComparePage />);
    fireEvent.click(runButton());
    await screen.findByRole("table", { name: "비교 표" });
    expect(historyStub.calls().filter((c) => c.method === "PUT")).toEqual([]);
  });
});

describe("자산군별 고르기", () => {
  it("예금은 투자처 체크박스다", async () => {
    route((path) => (path === "/api/deposit/institutions" ? { institutions: [] } : undefined));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("radio", { name: "예금" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: /시중은행/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /저축은행/ }));
    expect(useCompareStore.getState().targets).toEqual([{ institution: "commercial_bank" }, { institution: "savings_bank" }]);
  });

  it("부동산은 지역 풀다운을 받는다 — 비교 인스턴스로", async () => {
    const get = route((path) => (path.startsWith("/api/realestate/regions") ? { level: "sido", items: [] } : undefined));
    render(<ComparePage />);
    fireEvent.click(screen.getByRole("radio", { name: "부동산" }));
    await waitFor(() => expect(get.mock.calls.some(([p]) => p === "/api/realestate/regions")).toBe(true));
    expect(screen.getByText(/매입가는 대상마다 그 달 시세/)).toBeInTheDocument();
  });
});
