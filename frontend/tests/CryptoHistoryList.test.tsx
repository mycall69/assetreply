/**
 * 가상자산 이력과 비교 (T043) — 007 FR-045, FR-046, ui-wireframes(005 W5·W6과 같다).
 *
 * 이력 한 줄은 코인(한글·영문 이름과 심볼)·시작일·원금으로 구별한다 — 같은 심볼의 다른 코인이 같은 줄로 보이면 안 된다(FR-004).
 * 비교는 고른 이력을 **지금 다시 계산해서** 겹친다(결과를 저장하지 않으므로). 기준은 **모두 KRW 기준 수익률**이다(FR-046).
 * 다시 실행했는데 코인이 없으면(`unknown_coin`) "검색에서 다시 고르세요"를 말한다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { ApiError, apiClient } from "@/lib/apiClient";
import { loadCryptoHistory, saveCryptoHistory } from "@/lib/cryptoHistory";
import type { CryptoHistoryEntry } from "@/lib/types";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC, MAX_TOKEN } from "./support/coinSearchFixtures";
import { RESULT } from "./support/cryptoFixtures";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const SERIES = {
  from: "2020-01-15", to: "2021-12-31", principalCurrency: "USD", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: 2,
  points: [{ date: "2020-01-01", balance: "11566433", returnRate: "-0.000999" },
    { date: "2021-12-31", balance: "93745123", returnRate: "7.106116" }],
  gaps: [],
};

const entry = (over: Partial<CryptoHistoryEntry> = {}): CryptoHistoryEntry => ({
  id: "17|2020-01-15|10000|USD",
  coin: { coinId: BTC.coinId, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin",
    currency: "USD" },
  start: "2020-01-15", principal: "10000", principalCurrency: "USD", savedAt: "2026-10-04T00:00:00Z",
  ...over,
});

function renderHistory(entries: CryptoHistoryEntry[], selected: string[] = []) {
  const handlers = { onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn() };
  render(<CryptoHistory entries={entries} selected={selected} comparing={false} saveError={null}
    {...handlers} />);
  return handlers;
}

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
  useCryptoStore.getState().dispose();
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" },
    history: [], selectedHistory: [], comparison: [], comparisonError: null, error: null,
    summary: null, collecting: null,
  });
});

describe("이력 줄", () => {
  it("코인 이름·심볼·시작일·원금으로 구별하고 보관 위치를 알린다", () => {
    renderHistory([entry()]);
    const row = screen.getByTestId("history-row").textContent ?? "";
    expect(row).toContain("비트코인");
    expect(row).toContain("BTC");
    expect(row).toContain("2020-01-15");
    expect(row).toContain("10,000 USD");
    expect(screen.getByTestId("history-notice").textContent).toContain("이 브라우저에만");
  });

  it("한글 이름이 없으면 영문 이름이다", () => {
    renderHistory([entry({ id: "x", coin: { ...entry().coin, coinId: MAX_TOKEN.coinId,
      symbol: "MAX", name: "MAX Exchange Token", nameKo: null } })]);
    expect(screen.getByTestId("history-row").textContent).toContain("MAX Exchange Token");
  });

  it("막힌 원금 통화 조합이면 사유를 보인다", () => {
    renderHistory([entry({ principalCurrency: "JPY" })]);
    expect(screen.getByTestId("history-row").textContent).toContain("막힌 조합");
  });

  it("다시 실행·지우기·비교", async () => {
    const handlers = renderHistory([entry(), entry({ id: "y", start: "2021-01-01" })], ["17|2020-01-15|10000|USD"]);
    expect(screen.getByRole("button", { name: "선택 항목 비교" })).toBeDisabled();
    await userEvent.click(screen.getAllByRole("button", { name: /다시 실행/ })[0]);
    expect(handlers.onRerun).toHaveBeenCalledWith("17|2020-01-15|10000|USD");
    await userEvent.click(screen.getAllByRole("button", { name: /이력 삭제/ })[1]);
    expect(handlers.onRemove).toHaveBeenCalledWith("y");
  });
});

describe("저장소 — 이력", () => {
  it("결과가 나오면 조건을 이력에 남긴다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValueOnce(RESULT).mockResolvedValueOnce(SERIES);
    await useCryptoStore.getState().run();
    const [saved] = loadCryptoHistory();
    expect(saved.coin.coinId).toBe(BTC.coinId);
    expect(useCryptoStore.getState().history).toHaveLength(1);
  });

  it("수집 중(202)이면 남기지 않는다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ status: "collecting", coinId: BTC.coinId, jobId: 3 });
    await useCryptoStore.getState().run();
    expect(loadCryptoHistory()).toEqual([]);
  });

  it("다시 실행하면 그 조건으로 실행하고, 코인이 없으면 다시 고르라고 한다", async () => {
    saveCryptoHistory({ coin: { ...BTC, coinId: 404 }, start: "2019-05-01", principal: "500",
      principalCurrency: "USD" });
    useCryptoStore.getState().restoreHistory();
    const get = vi.spyOn(apiClient, "get").mockRejectedValue(new ApiError(404, "unknown_coin",
      "목록에서 찾을 수 없는 코인입니다(id 404).", { status: "unknown_coin", action: "reselect" }));
    await useCryptoStore.getState().rerunHistory(useCryptoStore.getState().history[0].id);
    expect(String(get.mock.calls[0][0])).toContain("coinId=404");
    expect(useCryptoStore.getState().input.start).toBe("2019-05-01");
    expect(useCryptoStore.getState().error).toContain("검색에서 다시 고르세요");
  });
});

describe("저장소 — 비교", () => {
  it("고른 이력을 지금 다시 계산해 겹치고 기준은 모두 KRW다", async () => {
    saveCryptoHistory({ coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" });
    saveCryptoHistory({ coin: MAX_TOKEN, start: "2021-06-01", principal: "10000000",
      principalCurrency: "KRW" });
    useCryptoStore.getState().restoreHistory();
    for (const e of useCryptoStore.getState().history) useCryptoStore.getState().toggleHistory(e.id);
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(SERIES);
    await useCryptoStore.getState().compareSelected();
    expect(get.mock.calls.every(([p]) => String(p).startsWith("/api/crypto/simulation/series?"))).toBe(true);
    const { comparison, comparisonError } = useCryptoStore.getState();
    expect(comparisonError).toBeNull();
    expect(comparison.map((c) => c.label)).toEqual(["MAX Exchange Token (MAX)", "비트코인 (BTC)"]);
    render(<ComparisonChart items={comparison} loading={false} error={null} />);
    expect(screen.getByTestId("comparison-basis").textContent).toContain("모두 KRW 기준");
    expect(screen.getByTestId("comparison-legend").textContent).toContain("2021-06-01 시작");
  });

  it("코인이 없거나 막힌 조합이면 빼되 사유를 말한다", async () => {
    saveCryptoHistory({ coin: BTC, start: "2020-01-15", principal: "10000", principalCurrency: "USD" });
    saveCryptoHistory({ coin: { ...MAX_TOKEN, coinId: 404 }, start: "2021-06-01", principal: "1",
      principalCurrency: "USD" });
    saveCryptoHistory({ coin: MAX_TOKEN, start: "2021-06-01", principal: "1", principalCurrency: "JPY" });
    useCryptoStore.getState().restoreHistory();
    for (const e of useCryptoStore.getState().history) useCryptoStore.getState().toggleHistory(e.id);
    vi.spyOn(apiClient, "get").mockImplementation(((path: string) => path.includes("coinId=404")
      ? Promise.reject(new ApiError(404, "unknown_coin", "목록에서 찾을 수 없는 코인입니다(id 404).",
        { status: "unknown_coin" }))
      : Promise.resolve(SERIES)) as typeof apiClient.get);
    await useCryptoStore.getState().compareSelected();
    const { comparison, comparisonError } = useCryptoStore.getState();
    expect(comparison).toHaveLength(1);
    expect(comparisonError).toContain("검색에서 다시 고르세요");
    expect(comparisonError).toContain("원금 JPY");
  });
});
