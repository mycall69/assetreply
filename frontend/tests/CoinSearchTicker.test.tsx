/**
 * 코인 검색 결과 줄의 이름(심볼) (014 반복 2026-10-10e T151) — FR-032, SC-017, contracts D11.
 *
 * 맨 앞 이름 뒤에 `(심볼)`을 붙인다 — 비교 화면과 가상자산 메뉴가 같은 부품이다. 영문 이름·`목록에서 빠짐`·오른쪽 `심볼 · 통화 #순위`는
 * 그대로다. 주식 검색 결과는 006 FR-025부터 이미 `이름(코드)`다(회귀 확인).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { StockSearch } from "@/components/stock/StockSearch";
import { BTC, BTS, response, routeSearch } from "./support/coinSearchFixtures";
import { SAMSUNG, local, routeGet } from "./support/stockSearchFixtures";

vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));

beforeEach(() => {
  vi.restoreAllMocks();
});

async function coinOptions(text: string) {
  render(<CoinSearch value={null} onSelect={vi.fn()} />);
  await userEvent.type(screen.getByRole("searchbox"), text);
  return screen.findAllByRole("option");
}

describe("코인 검색 결과 줄", () => {
  it("맨 앞이 한글 이름(심볼)이고 영문 이름이 뒤따른다", async () => {
    routeSearch(() => Promise.resolve(response([BTC])));
    const [option] = await coinOptions("ㅂㅌ");
    const text = option.textContent ?? "";
    expect(text.startsWith("비트코인(BTC)")).toBe(true);
    expect(text.indexOf("비트코인(BTC)")).toBeLessThan(text.indexOf("Bitcoin"));
  });

  it("한글 이름이 없으면 영문 이름(심볼)이다", async () => {
    routeSearch(() => Promise.resolve(response([BTS])));
    const [option] = await coinOptions("bts");
    expect((option.textContent ?? "").startsWith("BitShares(BTS)")).toBe(true);
  });

  it("오른쪽 심볼 · 통화 · 순위는 그대로다", async () => {
    routeSearch(() => Promise.resolve(response([BTC])));
    const [option] = await coinOptions("ㅂㅌ");
    expect(option.textContent).toContain("BTC · USD");
    expect(option.textContent).toContain("#1");
  });
});

describe("주식 검색 결과 줄 — 이미 이름(코드)", () => {
  it("삼성전자(005930)", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG])) });
    render(<StockSearch value={null} onSelect={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox"), "삼성");
    const option = await screen.findByRole("option", { name: /삼성전자/ });
    expect(option.textContent).toContain("삼성전자(005930)");
  });
});
