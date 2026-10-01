/**
 * 수집 중 안내 테스트 (T094) — 005 FR-047, FR-049, SC-029, ui-wireframes W7.
 *
 * **부분 결과를 먼저 보여주지 않는다.** 받은 만큼만 계산한 수익률은 값이 멀쩡해
 * 보이지만 틀린 값이고, 표에 숫자가 있으면 사용자는 그것을 최종 결과로 읽는다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CollectingNotice } from "@/components/stock/CollectingNotice";
import { apiClient } from "@/lib/apiClient";
import { useStockStore } from "@/stores/stockStore";
import type { SimulationCollecting } from "@/lib/types";

// jsdom에는 `EventSource`가 없다. 구독 자체는 `stockProgressStream`의 책임이고,
// 여기서 보려는 것은 **202를 받았을 때 결과를 비워 두는가**다.
vi.mock("@/lib/stockProgressStream", () => ({
  subscribeStockProgress: () => () => undefined,
}));

const COLLECTING: SimulationCollecting = {
  status: "collecting", market: "KRX", symbol: "005930.KS", jobId: 17,
  missingFrom: "2021-08-01", missingThrough: "2024-12-31",
  progressUrl: "/api/stocks/progress?jobId=17",
};

const base = { collecting: COLLECTING, stockName: "삼성전자", progress: null };

describe("수집 중 안내", () => {
  it("어느 종목을 받고 있는지 알린다", () => {
    render(<CollectingNotice {...base} />);
    expect(screen.getByRole("status").textContent).toContain("삼성전자");
  });

  it("받을 구간을 알린다", () => {
    // W7 — 얼마나 걸릴지 가늠할 근거가 없으면 사용자는 멈춘 것으로 읽는다.
    render(<CollectingNotice {...base} />);
    const text = screen.getByRole("status").textContent ?? "";
    expect(text).toContain("2021-08-01");
    expect(text).toContain("2024-12-31");
  });

  it("진행이 오면 진행률을 보인다", () => {
    render(
      <CollectingNotice {...base}
        progress={{ jobId: 17, chunksDone: 3, chunksTotal: 4,
          rangeStart: "2021-08-01", rangeEnd: "2024-12-31" }} />,
    );
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "3");
    expect(bar).toHaveAttribute("aria-valuemax", "4");
  });

  it("진행이 아직 없으면 그 사실을 말한다", () => {
    // 숫자를 0/0으로 보이면 멈춘 것처럼 읽힌다.
    render(<CollectingNotice {...base} />);
    expect(screen.getByRole("status").textContent).toContain("시작하는 중");
    expect(screen.queryByRole("progressbar")).toBeNull();
  });

  it("완료되면 결과가 표시된다고 알린다", () => {
    // 부분 결과를 안 보여주는 대신 기다릴 이유를 준다.
    render(<CollectingNotice {...base} />);
    expect(screen.getByRole("status").textContent).toContain("완료되면");
  });
});

describe("수집 중에는 결과를 두지 않는다", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useStockStore.setState({
      rows: [], summary: null, series: null, collecting: null,
      input: {
        stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
        start: "2021-08-01", principal: "86997",
        principalCurrency: "KRW", reinvest: true,
      },
    });
  });

  it("202가 오면 표와 차트를 비운 채로 둔다", async () => {
    // FR-049, SC-029 — 숫자가 보이면 사용자는 그것을 최종 결과로 읽는다.
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useStockStore.getState().run();

    const state = useStockStore.getState();
    expect(state.collecting).not.toBeNull();
    expect(state.rows).toEqual([]);
    expect(state.summary).toBeNull();
    expect(state.series).toBeNull();
    // 차트 시계열을 더 묻지 않는다 — 같은 구간에 수집 요청이 두 번 나간다.
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("수집 중이면 이력에 남기지 않는다", async () => {
    // 아직 결과가 없는 조건이다. 남기면 목록에 결과 없는 줄이 쌓인다.
    vi.spyOn(apiClient, "get").mockResolvedValue(COLLECTING);
    await useStockStore.getState().run();
    expect(useStockStore.getState().history).toEqual([]);
  });
});
