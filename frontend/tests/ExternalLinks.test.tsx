/**
 * 이름에서 외부 시세 페이지 — 부품 (010 반복 1, T045) — FR-024~FR-026, SC-007, ui-wireframes F5.
 *
 * 대상 여섯 — 고른 종목 줄(`StockSearch`)·주식 이력 행(`SimulationHistory`)·고른 코인(`CoinSearch`)·코인 이력 행(`CryptoHistory`)·부동산 보드
 * (`RealEstateBoard`)·부동산 이력 행(`RealEstateHistory`). 이름이 `<a target="_blank" rel="noopener noreferrer">`이고 href는 `lib/externalLinks`의
 * 규칙이다. 이력 행의 링크를 눌러도 행의 고르기·다시 실행이 일어나지 않는다. 검색 목록의 옵션은 링크가 아니다(누르면 고르기).
 *
 * 반복 3(FR-029) — 부동산 단지 이름은 검색 주소로 시작하고, 단지 번호 경로가 `found`를 주면 Npay 부동산의 그 단지 화면이 된다
 * (`ComplexLink.test.tsx`가 자세히 본다). 아래 부동산의 검색 기대는 "번호를 받기 전"이다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { RealEstateBoard } from "@/components/realestate/RealEstateBoard";
import { RealEstateHistory } from "@/components/realestate/RealEstateHistory";
import { SimulationHistory } from "@/components/stock/SimulationHistory";
import { StockSearch } from "@/components/stock/StockSearch";
import { apiClient } from "@/lib/apiClient";
import { coinLink, complexSearchLink, stockLink } from "@/lib/externalLinks";
import { resetNaverComplexLinks } from "@/lib/naverComplexLink";
import type { CryptoHistoryEntry, RealEstateHistoryEntry, SimulationHistoryEntry } from "@/lib/types";
import { SIM_RESULT } from "./support/realEstateSimulationFixtures";
import { SAMSUNG, local, routeGet } from "./support/stockSearchFixtures";

vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));

const NVDA = { market: "NASDAQ" as const, symbol: "NVDA", name: "엔비디아", currency: "USD" };
const BTC = { coinId: 1, symbol: "BTC", name: "Bitcoin", nameKo: "비트코인", slug: "bitcoin", currency: "USD" };
const handlers = () => ({ onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn() });

function expectExternal(link: HTMLElement, href: string | null) {
  expect(link.tagName).toBe("A");
  expect(link).toHaveAttribute("href", href ?? "");
  expect(link).toHaveAttribute("target", "_blank");
  expect(link).toHaveAttribute("rel", "noopener noreferrer");
}

beforeEach(() => {
  vi.restoreAllMocks();
  resetNaverComplexLinks();
});

describe("주식", () => {
  it("고른 종목 줄의 이름이 네이버 증권 링크다", () => {
    render(<StockSearch value={NVDA} onSelect={vi.fn()} />);
    expectExternal(screen.getByRole("link", { name: /엔비디아.*네이버 증권/ }), stockLink(NVDA));
  });

  it("검색 목록의 옵션은 링크가 아니다 — 누르면 고르기", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    const onSelect = vi.fn();
    render(<StockSearch value={null} onSelect={onSelect} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    const option = await screen.findByRole("option", { name: /삼성전자/ });
    expect(within(option).queryByRole("link")).toBeNull();
    await userEvent.click(option);
    expect(onSelect).toHaveBeenCalled();
  });

  it("이력 행의 종목 이름이 링크이고 눌러도 고르기·다시 실행이 일어나지 않는다", () => {
    const entry: SimulationHistoryEntry = { id: "n", stock: NVDA, start: "2020-01-02", principal: "10000000",
      principalCurrency: "KRW", reinvest: true, savedAt: "2026-10-05T00:00:00Z" };
    const props = handlers();
    render(<SimulationHistory entries={[entry]} selected={[]} comparing={false} saveError={null} {...props} />);
    const link = screen.getByRole("link", { name: /엔비디아.*네이버 증권/ });
    expectExternal(link, stockLink(NVDA));
    fireEvent.click(link);
    expect(props.onToggle).not.toHaveBeenCalled();
    expect(props.onRerun).not.toHaveBeenCalled();
  });

  it("규칙을 확인하지 못한 시장이면 링크 없이 이름만", () => {
    const entry: SimulationHistoryEntry = { id: "l", stock: { market: "LSE" as never, symbol: "VOD", name: "보다폰",
      currency: "GBP" }, start: "2020-01-02", principal: "1000", principalCurrency: "KRW", reinvest: true,
    savedAt: "2026-10-05T00:00:00Z" };
    render(<SimulationHistory entries={[entry]} selected={[]} comparing={false} saveError={null} {...handlers()} />);
    expect(screen.getByText("보다폰")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /보다폰/ })).toBeNull();
  });
});

describe("가상자산", () => {
  it("고른 코인 표시의 이름이 네이버 증권(업비트) 링크다", () => {
    render(<CoinSearch value={BTC} onSelect={vi.fn()} />);
    expectExternal(within(screen.getByTestId("coin-selected")).getByRole("link"), coinLink(BTC));
  });

  it("이력 행의 코인 이름이 링크이고 눌러도 행 동작이 없다", () => {
    const entry: CryptoHistoryEntry = { id: "c", coin: BTC, start: "2024-01-15", principal: "1000000",
      principalCurrency: "KRW", savedAt: "2026-10-05T00:00:00Z" };
    const props = handlers();
    render(<CryptoHistory entries={[entry]} selected={[]} comparing={false} saveError={null} {...props} />);
    const link = screen.getByRole("link", { name: /비트코인.*네이버 증권/ });
    expectExternal(link, coinLink(BTC));
    fireEvent.click(link);
    expect(props.onToggle).not.toHaveBeenCalled();
    expect(props.onRerun).not.toHaveBeenCalled();
  });
});

describe("부동산", () => {
  it("보드의 단지 이름이 네이버 검색 링크다 — 법정동 이름과 함께", () => {
    render(<RealEstateBoard result={SIM_RESULT} />);
    expectExternal(screen.getByRole("link", { name: /헬리오시티.*네이버에서 단지 찾기/ }),
      complexSearchLink(SIM_RESULT.complex.name, SIM_RESULT.complex.umdName));
  });

  const entry: RealEstateHistoryEntry = { id: "r", complexId: 12, complexName: "헬리오시티아파트", umd: "1171010700",
    area: "30k", areaLabel: "30평대(국평)", buyDate: "2021-03-15", buyPrice: null, savedAt: "2026-10-05T00:00:00Z" };

  it("이력 행 — 받아 둔 행정구역에 법정동이 있으면 이름을 붙인다, 눌러도 행 동작이 없다", () => {
    const props = handlers();
    render(<RealEstateHistory entries={[entry]} selected={[]} comparing={false} saveError={null}
      umdNames={{ "1171010700": "가락동" }} {...props} />);
    const link = screen.getByRole("link", { name: /헬리오시티아파트.*네이버에서 단지 찾기/ });
    expectExternal(link, complexSearchLink("헬리오시티아파트", "가락동"));
    fireEvent.click(link);
    expect(props.onToggle).not.toHaveBeenCalled();
    expect(props.onRerun).not.toHaveBeenCalled();
  });

  it("보드·이력 행 — 단지 번호를 찾으면 Npay 부동산 단지 화면이다(반복 3)", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      const id = Number(/complexes\/(\d+)\/naver/.exec(path)?.[1]);
      return { complexId: id, status: "found", url: `https://fin.land.naver.com/complexes/${id === 12 ? 111515 : 0}`,
        reason: null } as never;
    });
    render(<RealEstateHistory entries={[entry]} selected={[]} comparing={false} saveError={null} {...handlers()} />);
    expectExternal(await screen.findByRole("link", { name: /헬리오시티아파트 Npay 부동산에서 보기/ }),
      "https://fin.land.naver.com/complexes/111515");
  });

  it("이력 행 — 법정동 이름을 모르면 단지명만으로 검색한다", () => {
    render(<RealEstateHistory entries={[entry]} selected={[]} comparing={false} saveError={null} {...handlers()} />);
    expect(screen.getByRole("link", { name: /헬리오시티아파트.*네이버에서 단지 찾기/ }))
      .toHaveAttribute("href", complexSearchLink("헬리오시티아파트", null));
  });
});
