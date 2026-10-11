/**
 * 확대 구간의 일 단위 자료 — 끼워 그리기·받기 함수 (014 반복 2026-10-11c T193) — spec FR-038, SC-023, data-model 16, contracts A13.
 *
 * - 끼워 그리기: 구간 [from, to] 밖의 원래 점 + 받은 점(날짜 차례), 결측은 합친다(같은 구간은 한 번). 값은 받은 글자 그대로다
 * - 받는 그래프: 주식은 늘, 가상자산·외환은 받은 자료가 줄여졌을 때만, 예금·부동산은 받지 않는다. 주식·가상자산 경로에는 `viewFrom`·`viewTo`·
 *   `maxPoints=5000`, 외환은 `from`·`to`. 202는 받지 못한 것이다. 대상 여럿이면 받은 것만 끼우고, 하나도 못 받으면 실패다
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { historyDetailLoader, type ComparisonItem } from "@/components/stock/ComparisonChart";
import { apiClient } from "@/lib/apiClient";
import { covers, mergeGaps, spliceWindow, withDetail, withValueDetail } from "@/lib/chartDetail";
import {
  DETAIL_MAX_POINTS, compareDetailLoader, fetchFxDetail, fetchSeriesDetail, fxDetailPath, needsDetail, seriesDetailLoader, withView,
} from "@/lib/seriesDetail";
import type { SimulationSeriesResponse } from "@/lib/types";

const RANGE = { from: "2024-02-01", to: "2024-03-04" };

const series = (dates: string[], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: dates[0] ?? "2024-01-02", to: dates[dates.length - 1] ?? "2024-01-02", principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: dates.length,
  points: dates.map((date, i) => ({ date, balance: String(1000 + i), returnRate: "0.1" })), gaps: [], ...over,
});

const BASE = series(["2024-01-02", "2024-02-01", "2024-03-04", "2024-04-01"]);
const DAILY = series(["2024-02-01", "2024-02-02", "2024-02-05", "2024-03-04"],
  { gaps: [{ from: "2024-02-03", to: "2024-02-04", reason: "no_quote" }] });

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("끼워 그리기", () => {
  it("구간 밖은 원래 점, 구간 안은 받은 점이다 — 날짜 차례", () => {
    const merged = spliceWindow(BASE.points, DAILY.points, RANGE);
    expect(merged.map((p) => p.date)).toEqual(["2024-01-02", "2024-02-01", "2024-02-02", "2024-02-05", "2024-03-04", "2024-04-01"]);
    // 받은 점의 글자 그대로다 — 원래 점의 같은 날 값이 아니다.
    expect(merged.find((p) => p.date === "2024-02-01")?.balance).toBe(DAILY.points[0].balance);
  });

  it("결측은 합치고 같은 구간은 한 번이다", () => {
    const gap = { from: "2023-12-30", to: "2023-12-31", reason: "no_quote" as const };
    expect(mergeGaps([gap, DAILY.gaps[0]], DAILY.gaps)).toEqual([gap, DAILY.gaps[0]]);
  });

  it("시계열의 다른 칸은 원래 것이다", () => {
    const merged = withDetail({ ...BASE, downsampled: true, provisionalFrom: "2024-04-01" }, DAILY, RANGE);
    expect(merged.downsampled).toBe(true);
    expect(merged.provisionalFrom).toBe("2024-04-01");
    expect(merged.gaps).toEqual(DAILY.gaps);
  });

  it("현재 가치 선도 같은 구간을 끼우고 매도 후 금액은 원래 것이다", () => {
    const base = { points: [{ date: "2024-01-02", value: "1" }, { date: "2024-02-01", value: "2" }], afterSaleValue: "9" };
    const detail = { points: [{ date: "2024-02-01", value: "20" }, { date: "2024-02-02", value: "21" }], afterSaleValue: "0" };
    expect(withValueDetail(base, detail, RANGE)).toEqual({
      points: [{ date: "2024-01-02", value: "1" }, { date: "2024-02-01", value: "20" }, { date: "2024-02-02", value: "21" }],
      afterSaleValue: "9",
    });
  });

  it("받은 구간이 새 구간을 덮으면 다시 받지 않는다", () => {
    expect(covers(RANGE, { from: "2024-02-05", to: "2024-03-01" })).toBe(true);
    expect(covers(RANGE, { from: "2024-01-31", to: "2024-03-01" })).toBe(false);
    expect(covers(RANGE, { from: "2024-02-05", to: "2024-03-05" })).toBe(false);
  });
});

describe("받는 그래프", () => {
  it("주식은 늘, 가상자산·외환은 줄였을 때만, 예금·부동산은 받지 않는다", () => {
    const full = { downsampled: false };
    const reduced = { downsampled: true };
    expect(needsDetail("/api/stocks/simulation/series?x=1", full)).toBe(true);
    expect(needsDetail("/api/comparison/stocks/recurring-simulation?x=1", full)).toBe(true);
    expect(needsDetail("/api/crypto/simulation/series?x=1", full)).toBe(false);
    expect(needsDetail("/api/crypto/recurring-simulation/series?x=1", reduced)).toBe(true);
    expect(needsDetail("/api/comparison/crypto/simulation?x=1", reduced)).toBe(true);
    expect(needsDetail("/api/fx/series?currency=USD", reduced)).toBe(true);
    expect(needsDetail("/api/deposit/simulation/series?x=1", reduced)).toBe(false);
    expect(needsDetail("/api/realestate/simulation/series?x=1", reduced)).toBe(false);
  });

  it("보기 구간 질의와 넉넉한 점 수를 붙인다", () => {
    expect(DETAIL_MAX_POINTS).toBe(5000);
    expect(withView("/api/stocks/simulation/series?market=KRX", RANGE))
      .toBe("/api/stocks/simulation/series?market=KRX&viewFrom=2024-02-01&viewTo=2024-03-04&maxPoints=5000");
    expect(fxDetailPath("JPY", RANGE)).toBe("/api/fx/series?currency=JPY&from=2024-02-01&to=2024-03-04&maxPoints=5000");
  });

  it("받지 않는 그래프면 받기 함수가 없다", () => {
    expect(seriesDetailLoader(null, BASE)).toBeUndefined();
    expect(seriesDetailLoader("/api/stocks/simulation/series?a=1", null)).toBeUndefined();
    expect(seriesDetailLoader("/api/crypto/simulation/series?a=1", BASE)).toBeUndefined();
    expect(seriesDetailLoader("/api/stocks/simulation/series?a=1", BASE)).toBeTypeOf("function");
  });
});

describe("받기", () => {
  it("주식·외환 구간을 그 경로로 받는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(DAILY);
    await expect(fetchSeriesDetail("/api/stocks/simulation/series?a=1", RANGE)).resolves.toBe(DAILY);
    await fetchFxDetail("USD", RANGE);
    expect(get.mock.calls.map((c) => c[0])).toEqual([
      "/api/stocks/simulation/series?a=1&viewFrom=2024-02-01&viewTo=2024-03-04&maxPoints=5000",
      "/api/fx/series?currency=USD&from=2024-02-01&to=2024-03-04&maxPoints=5000",
    ]);
  });

  it("202(수집 중)는 받지 못한 것이다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ status: "collecting" });
    await expect(fetchSeriesDetail("/api/stocks/simulation/series?a=1", RANGE)).rejects.toThrow();
  });

  it("투자 비교는 받을 대상만 받고, 받은 대상만 돌려준다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(((path: string) => (path.includes("000660")
      ? Promise.reject(new Error("fail"))
      : Promise.resolve({ series: DAILY, comparison: { valueLine: { points: [], afterSaleValue: null } } }))) as typeof apiClient.get);
    const load = compareDetailLoader([
      { key: "a", path: "/api/comparison/stocks/simulation?symbol=005930.KS", series: BASE },
      { key: "b", path: "/api/comparison/stocks/simulation?symbol=000660.KS", series: BASE },
      { key: "c", path: "/api/comparison/crypto/simulation?coinId=1", series: BASE },
    ]);
    const detail = await load?.(RANGE);
    expect(Object.keys(detail ?? {})).toEqual(["a"]);
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("투자 비교에서 하나도 받지 못하면 실패다", async () => {
    vi.spyOn(apiClient, "get").mockRejectedValue(new Error("fail"));
    const load = compareDetailLoader([{ key: "a", path: "/api/comparison/stocks/simulation?x=1", series: BASE }]);
    await expect(load?.(RANGE)).rejects.toThrow();
    expect(compareDetailLoader([{ key: "c", path: "/api/comparison/crypto/simulation?x=1", series: BASE }])).toBeUndefined();
  });

  it("이력 비교는 경로가 있는 받을 항목만 받는다", async () => {
    const get = vi.spyOn(apiClient, "get").mockResolvedValue(DAILY);
    const items: ComparisonItem[] = [
      { id: "s", label: "삼성전자", start: "2024-01-02", series: BASE, path: "/api/stocks/simulation/series?a=1" },
      { id: "d", label: "시중은행", start: "2024-01-02", series: BASE, path: "/api/deposit/simulation/series?a=1" },
      { id: "x", label: "경로 없음", start: "2024-01-02", series: BASE },
    ];
    const detail = await historyDetailLoader(items)?.(RANGE);
    expect(Object.keys(detail ?? {})).toEqual(["s"]);
    expect(get).toHaveBeenCalledTimes(1);
    expect(historyDetailLoader(items.slice(1))).toBeUndefined();
  });
});
