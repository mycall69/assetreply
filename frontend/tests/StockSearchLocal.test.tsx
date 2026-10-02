/**
 * 로컬 목록 검색 결과 (T027) — 006 FR-024, FR-025, FR-028, FR-028a, FR-029, FR-029a, SC-006,
 * contracts/ui-wireframes W2·W2a.
 *
 * **"결과 없음"과 "목록 없음"을 가른다.** 같은 빈 화면이 "그런 종목이 없다"와 "목록이 없다"를
 * 함께 뜻하면, 사용자는 할 일이 정반대인데 구별할 수 없다.
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import type { ListingUnitStatus } from "@/lib/types";
import {
  DELISTED,
  KODEX200,
  REIT,
  SAMSUNG,
  SAMSUNG_PREF,
  local,
  routeGet,
} from "./support/stockSearchFixtures";

beforeEach(() => {
  vi.restoreAllMocks();
});

async function typeQuery(text: string) {
  render(<StockSearch value={null} onSelect={vi.fn()} />);
  await userEvent.type(screen.getByRole("searchbox"), text);
}

const localRegion = () => screen.getByRole("region", { name: "국내·미국" });

describe("결과 표시", () => {
  it("결과마다 시장과 통화, 코드를 보인다", async () => {
    // FR-025, 005 FR-002b — 같은 이름이 여러 시장에 있고, 통화가 다르면 환전 여부가 다르다.
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    await typeQuery("삼성");
    const option = await screen.findByRole("option", { name: /삼성전자/ });
    expect(option.textContent).toContain("KRX");
    expect(option.textContent).toContain("KRW");
    expect(option.textContent).toContain("005930");
  });

  it("보통주와 우선주가 함께 나오되 구별된다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, SAMSUNG_PREF])) });
    await typeQuery("ㅅㅅㅈㅈ");
    const options = await within(localRegion()).findAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      expect.stringContaining("005930"),
      expect.stringContaining("005935"),
    ]);
    expect(options[1].textContent).toContain("삼성전자우");
  });

  it("ETF와 리츠를 글자로 표시한다", async () => {
    // 색만으로 전달하지 않는다 (ui-wireframes 접근성).
    routeGet({ local: () => Promise.resolve(local([KODEX200, REIT])) });
    await typeQuery("ㄷ");
    const etf = await screen.findByRole("option", { name: /KODEX 200/ });
    expect(etf.textContent).toContain("ETF");
    expect(screen.getByRole("option", { name: /대신밸류리츠/ }).textContent).toContain("리츠");
  });

  it("목록에서 빠진 종목을 글자로 표시한다", async () => {
    // FR-019, FR-025 — 지우지 않고 남긴 종목이 정상 종목처럼 보이면 안 된다.
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, DELISTED])) });
    await typeQuery("삼성");
    const option = await screen.findByRole("option", { name: /삼성옛종목/ });
    expect(option.textContent).toContain("목록에서 빠짐");
    expect(screen.getByRole("option", { name: /^삼성전자/ }).textContent)
      .not.toContain("목록에서 빠짐");
  });

  it("잘렸으면 더 있다고 알린다", async () => {
    // FR-024 — 숨기면 사용자는 찾는 종목이 없다고 읽는다.
    routeGet({ local: () => Promise.resolve(local([SAMSUNG], { truncated: true })) });
    await typeQuery("ㅅ");
    expect(await within(localRegion()).findByText(/결과가 더 있습니다/)).toBeInTheDocument();
  });

  it("목록의 기준 시각을 보인다", async () => {
    // FR-029 — 없으면 오늘 상장한 종목이 안 보일 때 목록이 낡은 것인지 판단할 수 없다.
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    await typeQuery("삼성");
    const line = await within(localRegion()).findByTestId("listing-asof");
    // 한국 시간으로 보인다 (00:05 UTC = 09:05 KST)
    expect(line.textContent).toContain("KOSPI");
    expect(line.textContent).toContain("10-02 09:05");
    expect(line.textContent).toContain("KOSDAQ");
  });

  it("갱신 중이면 기준 시각과 함께 그 사실을 보인다", async () => {
    // FR-017 — 이전 목록으로 답한다는 것을 숨기지 않는다.
    const lists: ListingUnitStatus[] = [
      { unit: "KOSPI", state: "refreshing", asOf: "2026-10-01T00:05:12Z", action: "wait" },
      { unit: "KOSDAQ", state: "ready", asOf: "2026-10-02T00:05:40Z" },
    ];
    routeGet({ local: () => Promise.resolve(local([SAMSUNG], { lists })) });
    await typeQuery("삼성");
    const line = await within(localRegion()).findByTestId("listing-asof");
    expect(line.textContent).toMatch(/KOSPI[^·]*갱신 중/);
    expect(line.textContent).toContain("10-01 09:05");
  });
});

describe("결과가 비었을 때", () => {
  it("목록이 모두 있으면 결과 없음이라고 말한다", async () => {
    routeGet({ local: () => Promise.resolve(local([])) });
    await typeQuery("ㅋㅋㅋ");
    expect(await within(localRegion()).findByText(/해당하는 종목을 찾지 못했습니다/))
      .toBeInTheDocument();
  });

  it("인증 정보가 없으면 결과 없음이 아니라 할 일을 말한다", async () => {
    // SC-006, FR-028a, W2a.
    const lists: ListingUnitStatus[] = [
      { unit: "KOSPI", state: "never", asOf: null, reason: "auth_missing",
        action: "set_credentials" },
      { unit: "KOSDAQ", state: "never", asOf: null, reason: "auth_missing",
        action: "set_credentials" },
    ];
    routeGet({ local: () => Promise.resolve(local([], { lists })) });
    await typeQuery("삼성");
    const notice = await within(localRegion()).findByTestId("listing-notice");
    expect(notice.textContent).toMatch(/목록을 받지 못했습니다/);
    expect(notice.textContent).toMatch(/인증 정보가 설정되지 않았습니다/);
    expect(notice.textContent).toContain("KIWOOM_APP_KEY");
    expect(notice.textContent).toMatch(/다시 시작/);
    expect(within(localRegion()).queryByText(/찾지 못했습니다/)).toBeNull();
  });

  it("받는 중이면 기다리라고 말한다", async () => {
    const lists: ListingUnitStatus[] = [
      { unit: "KOSPI", state: "refreshing", asOf: null, action: "wait" },
      { unit: "KOSDAQ", state: "ready", asOf: "2026-10-02T00:05:40Z" },
    ];
    routeGet({ local: () => Promise.resolve(local([], { lists })) });
    await typeQuery("삼성");
    const notice = await within(localRegion()).findByTestId("listing-notice");
    expect(notice.textContent).toMatch(/KOSPI/);
    expect(notice.textContent).toMatch(/받는 중/);
    expect(within(localRegion()).queryByText(/해당하는 종목을 찾지 못했습니다/)).toBeNull();
  });

  it("인증 실패면 인증 정보를 확인하라고 말한다", async () => {
    const lists: ListingUnitStatus[] = [
      { unit: "KOSPI", state: "auth_blocked", asOf: null, reason: "auth_failed",
        action: "set_credentials" },
      { unit: "KOSDAQ", state: "auth_blocked", asOf: null, reason: "auth_failed",
        action: "set_credentials" },
    ];
    routeGet({ local: () => Promise.resolve(local([], { lists })) });
    await typeQuery("삼성");
    const notice = await within(localRegion()).findByTestId("listing-notice");
    expect(notice.textContent).toMatch(/인증에 실패했습니다/);
    expect(within(localRegion()).queryByText(/해당하는 종목을 찾지 못했습니다/)).toBeNull();
  });

  it("받지 못했으면 잠시 뒤 다시 하라고 말한다", async () => {
    const lists: ListingUnitStatus[] = [
      { unit: "KOSPI", state: "never", asOf: null, reason: "network", action: "retry_later" },
      { unit: "KOSDAQ", state: "ready", asOf: "2026-10-02T00:05:40Z" },
    ];
    routeGet({ local: () => Promise.resolve(local([], { lists })) });
    await typeQuery("삼성");
    const notice = await within(localRegion()).findByTestId("listing-notice");
    expect(notice.textContent).toMatch(/잠시 뒤/);
  });

  it("검색 자체가 실패하면 결과 없음과 다르게 말한다", async () => {
    routeGet({ local: () => Promise.reject(new Error("연결 실패")) });
    await typeQuery("삼성");
    expect(await within(localRegion()).findByRole("alert")).toBeInTheDocument();
    expect(within(localRegion()).queryByText(/찾지 못했습니다/)).toBeNull();
  });
});

describe("늦게 온 결과", () => {
  it("이전 검색어의 응답이 늦게 와도 최신 결과를 덮지 않는다", async () => {
    // FR-029a — 사용자는 지금 친 검색어의 결과로 읽는다.
    let releaseSlow: (value: unknown) => void = () => {};
    routeGet({
      local: (path) => {
        if (path.includes(encodeURIComponent("삼성전자"))) {
          return Promise.resolve(local([SAMSUNG], { query: "삼성전자" }));
        }
        return new Promise((resolve) => {
          releaseSlow = resolve;
        });
      },
    });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    const box = screen.getByRole("searchbox");
    await userEvent.type(box, "삼");
    await new Promise((r) => setTimeout(r, 250));     // "삼"의 요청이 나간다
    await userEvent.type(box, "성전자");
    await screen.findByRole("option", { name: /삼성전자/ });

    releaseSlow(local([DELISTED], { query: "삼" }));
    await new Promise((r) => setTimeout(r, 20));
    await waitFor(() => {
      expect(screen.queryByRole("option", { name: /삼성옛종목/ })).toBeNull();
    });
    expect(screen.getByRole("option", { name: /삼성전자/ })).toBeInTheDocument();
  });
});
