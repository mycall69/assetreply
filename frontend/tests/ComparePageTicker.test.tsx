/**
 * 투자 비교 화면의 티커 표시 — 끝에서 끝까지 (014 반복 2026-10-10e T151) — FR-032, SC-017, contracts D11.
 *
 * 이름 자리 — 비교 대상 칩·비교 표·막힘 안내·수익률 범례·최종 지표 막대(잘리면 `title`)·투자 시뮬레이션 모달 머리·저장한 비교 목록 —
 * 와 그 이름을 쓰는 화면 읽기 이름이 모두 같은 "이름(티커)"다. 자리마다 따로 만들면 같은 대상이 두 이름으로 보인다.
 * 이름은 저장하지 않는다 — 이 반복 전에 저장한 비교를 불러와도 티커가 붙는다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ComparePage from "@/app/compare/page";
import type { StockTarget } from "@/lib/types";
import { useCompareDetailStore } from "@/stores/compareDetailStore";
import { useCompareStore } from "@/stores/compareStore";
import { SERIES, STOCK_LUMP } from "./support/compareDetailFixtures";
import { BTC_T, ETH_T, SAMSUNG_T, apiError, ok, routeCompare } from "./support/compareFixtures";
import { savedComparisonStub } from "./support/savedComparisonStub";

vi.mock("@/lib/stockProgressStream", () => ({ subscribeStockProgress: () => () => undefined }));
vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
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

const VOO_T: StockTarget = { market: "NYSE", symbol: "VOO", name: "S&P 500 뱅가드 ETF", currency: "USD" };
const VOO = "S&P 500 뱅가드 ETF(VOO)";
const SAMSUNG = "삼성전자(005930)";

function route(blockVoo = false) {
  return routeCompare((path) => {
    if (path.startsWith("/api/stocks/search")) return { query: "", results: [], truncated: false, lists: [] };
    if (path.startsWith("/api/crypto/search")) return { query: "", results: [], truncated: false, list: { state: "ready" } };
    if (path.startsWith("/api/comparison/crypto/")) return ok(path.includes("coinId=18") ? ETH_T : BTC_T);
    if (path.startsWith("/api/comparison/")) {
      if (path.includes("VOO")) {
        return blockVoo ? apiError(400, "before_listing", { startableFrom: "2010-09-09", basis: "listing" }) : ok(VOO_T);
      }
      return ok(SAMSUNG_T);
    }
    if (path.includes("/series")) return SERIES;
    if (path.startsWith("/api/stocks/simulation?")) return STOCK_LUMP;
    return undefined;
  });
}

function fresh(): void {
  useCompareDetailStore.setState(useCompareDetailStore.getInitialState(), true);
  useCompareStore.getState().dispose();
  useCompareStore.setState(useCompareStore.getInitialState(), true);
  useCompareStore.setState({ start: "2020-01-02" });
}

beforeEach(() => {
  vi.restoreAllMocks();
  fresh();
});

async function runWith(...targets: Parameters<ReturnType<typeof useCompareStore.getState>["addTarget"]>[0][]) {
  for (const t of targets) useCompareStore.getState().addTarget(t);
  render(<ComparePage />);
  fireEvent.click(screen.getByRole("button", { name: "비교 실행" }));
}

describe("주식 — 이름 자리가 모두 같은 이름(티커)", () => {
  it("칩·빼기 단추·비교 표·투자 시뮬레이션 단추", async () => {
    route();
    await runWith(VOO_T, SAMSUNG_T);
    const chips = screen.getByRole("list", { name: "고른 비교 대상" });
    expect(within(chips).getByText(VOO)).toBeInTheDocument();
    expect(within(chips).getByText(SAMSUNG)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${VOO} 빼기` })).toBeInTheDocument();

    const table = await screen.findByRole("table", { name: "비교 표" });
    expect(within(table).getByText(VOO)).toBeInTheDocument();
    expect(within(table).getByText(SAMSUNG)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `${VOO} 투자 시뮬레이션` })).toBeInTheDocument();
  });

  it("수익률 범례와 최종 지표 막대(잘리면 마우스를 올려 전체 이름)", async () => {
    route();
    await runWith(VOO_T, SAMSUNG_T);
    await screen.findByRole("table", { name: "비교 표" });
    const legend = await screen.findByTestId("compare-legend");
    expect(legend.textContent).toContain(VOO);
    expect(legend.textContent).toContain(SAMSUNG);
    const bars = screen.getByTestId("compare-bars");
    const titled = within(bars).getAllByTitle(VOO);
    expect(titled.length).toBeGreaterThan(0);
    for (const label of titled) expect(label.textContent).toBe(VOO);
  });

  it("투자 시뮬레이션 모달 머리", async () => {
    route();
    await runWith(VOO_T, SAMSUNG_T);
    await screen.findByRole("table", { name: "비교 표" });
    fireEvent.click(screen.getByRole("button", { name: `${VOO} 투자 시뮬레이션` }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("heading", { level: 2 }).textContent).toContain(VOO);
  });

  it("막힘 안내", async () => {
    route(true);
    await runWith(VOO_T, SAMSUNG_T);
    const alert = await screen.findByRole("alert", { name: "비교할 수 없습니다" });
    expect(alert.textContent).toContain(`${VOO} — `);
  });
});

describe("가상자산 — 한글 이름(심볼)", () => {
  it("칩·비교 표·범례", async () => {
    route();
    useCompareStore.getState().setAsset("crypto");
    await runWith(BTC_T, ETH_T);
    const chips = screen.getByRole("list", { name: "고른 비교 대상" });
    expect(within(chips).getByText("비트코인(BTC)")).toBeInTheDocument();
    expect(within(chips).getByText("이더리움(ETH)")).toBeInTheDocument();
    const table = await screen.findByRole("table", { name: "비교 표" });
    expect(within(table).getByText("비트코인(BTC)")).toBeInTheDocument();
    expect((await screen.findByTestId("compare-legend")).textContent).toContain("이더리움(ETH)");
  });
});

describe("저장한 비교 — 이름을 저장하지 않는다", () => {
  it("이 반복 전에 저장한 조건도 목록과 불러온 칩에 티커가 붙는다", async () => {
    route();
    savedComparisonStub.seed([{
      name: "S&P 500과 삼성",
      condition: {
        v: 1, asset: "stock", method: "lump_sum", frequency: null, start: "2020-01-02", amount: "10000000",
        principalCurrency: "KRW", reinvest: true, targets: [VOO_T, SAMSUNG_T],
      },
    }]);
    render(<ComparePage />);
    const saved = screen.getByRole("region", { name: "저장한 비교" });
    expect(await within(saved).findByText(`주식 · ${VOO}, ${SAMSUNG}`)).toBeInTheDocument();
    fireEvent.click(within(saved).getByRole("button", { name: "S&P 500과 삼성 불러오기" }));
    const chips = await screen.findByRole("list", { name: "고른 비교 대상" });
    expect(within(chips).getByText(VOO)).toBeInTheDocument();
  });
});
