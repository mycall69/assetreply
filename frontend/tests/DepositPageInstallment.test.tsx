/**
 * 예금 화면의 정기 적금 — 화면 → 스토어 → 경로 (011 T045) — FR-022, FR-023, FR-029, FR-031, FR-032, SC-009.
 *
 * **실제로 눌러야만 통과한다**(006 D1): 화면이 상품 칸을 그리지 않거나, 스토어가 상품을 받지 않거나, 실행이 적금 경로를 부르지 않으면 이 테스트가
 * 실패한다.
 * - 결과가 오면 여섯 칸 보드·적금 표·적금 부제목이 보이고, 정기예금 보드는 없다
 * - 금액 칸 이름이 "월 납입액"이 되고, 적금이 없는 투자처는 고를 수 없다
 * - 이력 행은 "정기 적금 · 월 ₩…"이다. 정기예금 부제목 검사(`DepositPage.test.tsx`)는 그대로다
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DepositPage from "@/app/deposit/page";
import { apiClient } from "@/lib/apiClient";
import type { SimulationSeriesResponse } from "@/lib/types";
import { useDepositStore } from "@/stores/depositStore";
import { INSTALLMENT_INSTITUTIONS, INSTALLMENT_RESULT } from "./support/installmentFixtures";

vi.mock("@/lib/depositProgressStream", () => ({ subscribeDepositProgress: () => () => undefined }));
// 실제 차트는 jsdom에서 그릴 수 없다(`matchMedia` 없음). 범례는 DOM이라 모의로도 보인다.
vi.mock("lightweight-charts", () => ({
  LineSeries: "Line",
  createChart: () => ({
    addSeries: () => ({ setData: () => undefined }),
    subscribeCrosshairMove: () => undefined,
    timeScale: () => ({ fitContent: () => undefined }),
    remove: () => undefined,
  }),
}));

const SERIES: SimulationSeriesResponse = {
  from: "2015-01-15", to: "2018-01-15", principalCurrency: "KRW", basisCurrency: "KRW", downsampled: false,
  algorithm: "lttb", sourcePointCount: 1, priceKind: "installment_rate", priceCurrency: null,
  points: [{ date: "2018-01-15", balance: "37811149", returnRate: "0.021923", principal: "37000000", price: "1.82",
    depositRate: "1.93" }],
  gaps: [], provisionalFrom: null,
};

const SUBTITLE = "매달 정해진 돈을 1년 만기 정기 적금에 붓고, 만기 금액은 1년 정기예금에 넣으며 새 적금을 붓는 성과";

beforeEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
  useDepositStore.setState({
    input: { institution: "commercial_bank", start: "2015-01-15", principal: "1000000" },
    product: "deposit", installment: null, productNotice: null,
    rows: [], summary: null, condition: null, collecting: null, progress: null, error: null, startable: null,
    loading: false, history: [], selectedHistory: [], comparison: [],
  });
});

describe("예금 화면 — 정기 적금", () => {
  it("정기 적금을 고르고 실행하면 적금 경로로 요청하고 여섯 칸 보드와 적금 표가 보인다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.startsWith("/api/deposit/institutions")) return INSTALLMENT_INSTITUTIONS as never;
      return (path.includes("/series") ? SERIES : INSTALLMENT_RESULT) as never;
    });
    render(<DepositPage />);
    expect(screen.getByText("투자 원금")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("radio", { name: "정기 적금" }));
    expect(screen.getByText(SUBTITLE)).toBeInTheDocument();
    expect(screen.getByText("월 납입액")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole("radio", { name: "저축은행" })).toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "시뮬레이션" }));

    await waitFor(() => expect(get).toHaveBeenCalledWith(
      "/api/deposit/installment-simulation?institution=commercial_bank&start=2015-01-15&amount=1000000"));
    expect(await screen.findByRole("group", { name: "총 납입 원금" })).toHaveTextContent("₩37,000,000");
    expect(screen.getByRole("group", { name: "세후 이자 합계" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "평가액" })).toBeInTheDocument();
    expect(screen.getAllByRole("row").some((r) => r.getAttribute("data-kind") === "deposit_join")).toBe(true);
    expect(screen.getByTestId("chart-legend")).toHaveTextContent("누적 납입 원금");
    expect(screen.getAllByTestId("history-row")[0]).toHaveTextContent("정기 적금 · 월 ₩1,000,000");
  });

  it("누르지 않으면 적금 경로를 부르지 않고 부제목은 정기예금이다", async () => {
    vi.spyOn(apiClient, "get").mockResolvedValue(INSTALLMENT_INSTITUTIONS as never);
    render(<DepositPage />);
    expect(screen.queryByText(SUBTITLE)).toBeNull();
    expect(screen.getByText(/1년 만기 정기예금에 가입하고 만기마다 세후 이자를 더해 재예치한 성과/)).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "정기예금" })).toBeChecked();
  });
});
