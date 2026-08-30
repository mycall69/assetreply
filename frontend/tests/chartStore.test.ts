/**
 * 차트 상태 스토어 테스트 (T120).
 *
 * FR-002: 축적 시작일은 통화마다 다르다. 따라서 "전체" 프리셋의 시작일을
 * 클라이언트가 상수로 알 수 없다 — 커버리지에서 받아와야 한다.
 * FR-029: 프리셋과 직접 지정 두 방식을 제공한다.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import { presetRange, useChartStore } from "@/stores/chartStore";

describe("차트 기간 프리셋", () => {
  it("전체 프리셋은 시작일을 비워 둔다", () => {
    // 통화별 최초 제공일이 다르므로(USD 1964, EUR 1994) 상수를 둘 수 없다.
    expect(presetRange("all").from).toBe("");
  });

  it("상대 기간 프리셋은 날짜를 계산한다", () => {
    expect(presetRange("1y").from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(presetRange("5y").from).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });
});

describe("전체 구간 조회", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    useChartStore.setState({
      currency: "USD",
      preset: "all",
      ...presetRange("all"),
      data: null,
      collecting: null,
      error: null,
    });
  });

  it("커버리지의 최초 제공일부터 조회한다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.startsWith("/api/fx/coverage")) {
        return {
          coverage: [{
            currency: "USD",
            coveredFrom: "1964-01-01",
            coveredThrough: "2026-08-29",
            firstAvailableDate: "1964-05-04",
            lastUpdatedAt: "2026-08-30T01:12:00Z",
          }],
        };
      }
      return { currency: "USD", points: [], gaps: [], downsampled: false };
    });

    await useChartStore.getState().fetchSeries();

    const seriesCall = get.mock.calls.map(String).find((p) => p.includes("/api/fx/series"));
    expect(seriesCall).toContain("from=1964-05-04");
    expect(useChartStore.getState().from).toBe("1964-05-04");
  });

  it("최초 제공일이 아직 없으면 수집 완료 구간 시작을 쓴다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.startsWith("/api/fx/coverage")) {
        return {
          coverage: [{
            currency: "USD",
            coveredFrom: "1964-01-01",
            coveredThrough: "2026-08-29",
            firstAvailableDate: null,
            lastUpdatedAt: "2026-08-30T01:12:00Z",
          }],
        };
      }
      return { currency: "USD", points: [], gaps: [], downsampled: false };
    });

    await useChartStore.getState().fetchSeries();

    const seriesCall = get.mock.calls.map(String).find((p) => p.includes("/api/fx/series"));
    expect(seriesCall).toContain("from=1964-01-01");
  });

  it("수집된 데이터가 없으면 안내한다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue({ coverage: [] });

    await useChartStore.getState().fetchSeries();

    expect(useChartStore.getState().error).toMatch(/수집된 데이터가 없습니다/);
  });
});
