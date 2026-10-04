/**
 * 가상자산 성과 보드의 원금 통화 (T036) — 007 FR-034~FR-036, FR-042, ui-wireframes C3.
 *
 * 투자 수익·수익률은 원금 통화와 관계없이 **KRW 기준**이다. 달러 원금이면 원금 옆 괄호에 KRW 값(첫 매수일 매매기준율 —
 * 수익률의 분모), 원화 원금이면 **환전 줄**(현금 살 때 환율과 그 날짜, 우대)이 붙는다. 006의 보드를 그대로 쓴다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CryptoPage from "@/app/crypto/page";
import { useCryptoStore } from "@/stores/cryptoStore";
import { BTC } from "./support/coinSearchFixtures";
import { RESULT } from "./support/cryptoFixtures";

vi.mock("@/lib/cryptoProgressStream", () => ({ subscribeCryptoProgress: () => () => undefined }));
vi.mock("@/lib/cryptoListProgressStream", () => ({
  subscribeCoinListProgress: () => () => undefined }));
vi.mock("@/lib/collectionStream", () => ({ subscribeCollection: () => () => undefined }));

/** 성과 보드 — "투자 원금"은 입력 폼의 칸 이름이기도 하다. 칸 셋이 든 구역으로 찾는다. */
const board = () => screen.getAllByText("투자 원금").map((el) => el.closest("section"))
  .find((s) => s?.querySelector("div.grid") !== null) as HTMLElement;

function show(principalCurrency: "USD" | "KRW") {
  const krw = principalCurrency === "KRW";
  useCryptoStore.setState({
    input: { coin: BTC, start: "2020-01-15", principal: krw ? "10000000" : "10000",
      principalCurrency },
    rows: RESULT.rows,
    condition: { ...RESULT.condition, principal: krw ? "10000000" : "10000", principalCurrency },
    summary: krw
      ? { ...RESULT.summary, principal: "10000000", principalKrw: undefined }
      : RESULT.summary,
    exchange: krw
      ? { rate: "1159.884000", rateDate: "2019-12-31", kind: "cash_buy_discounted",
        spreadDiscount: "0.9" }
      : null,
    collecting: null, error: null, loading: false,
  });
  // 화면이 열릴 때 다시 받지 않게 한다 — 여기서 보려는 것은 보드의 표기다.
  useCryptoStore.setState({ refreshIfRan: async () => undefined });
  render(<CryptoPage />);
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("성과 보드 — 원금 통화", () => {
  it("달러 원금이면 원금 옆에 KRW 값이 붙고 환전 줄이 없다", () => {
    show("USD");
    const text = board().textContent ?? "";
    expect(text).toContain("10,000$");
    expect(text).toContain("(11,564,000₩)");
    expect(text).toContain("82,175,123₩");
    expect(text).toContain("KRW 기준");
    expect(text).not.toContain("환전");
  });

  it("원화 원금이면 환전 줄이 붙는다 — 그 날짜와 우대", () => {
    show("KRW");
    const text = board().textContent ?? "";
    expect(text).toContain("10,000,000₩");
    // 원화 원금에는 KRW 괄호가 없다 — 같은 값을 두 번 쓰지 않는다
    expect(text).not.toMatch(/10,000,000₩\s*\(/);
    expect(text).toContain("환전 2019-12-31 현금 살 때 1,159.88");
    expect(text).toContain("90% 우대");
  });

  it("기준 줄에 매수일과 수수료가 있다", () => {
    show("USD");
    const text = board().textContent ?? "";
    expect(text).toContain("매수일 2020-01-01");
    expect(text).toContain("수수료 0.10%");
  });
});
