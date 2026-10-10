/**
 * 주식 검색 결과 줄의 상장일 (014 반복 2026-10-10f T160) — FR-033, contracts D12, research R14-26.
 *
 * 기준을 줄 안에서 밝힌다 — 키움 국내 상장일은 `상장 …`, 저장된 Yahoo 첫 거래일은 `첫 거래 …`다. Yahoo 첫 거래일은 출처가 시세를 가진
 * 첫 날이라 오래된 종목은 상장일보다 늦다(T158 — 도요타 1999-05-06). 둘 다 없으면 그 글자를 뺀다(지어내지 않는다).
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import type { LocalStockResult } from "@/lib/types";
import { SAMSUNG, external, local, routeGet } from "./support/stockSearchFixtures";

const SPY: LocalStockResult = {
  ...SAMSUNG, listingId: 5001, country: "US", market: "NYSE", symbol: "SPY", code: "SPY",
  name: "S&P 500 SPDR ETF", nameEn: "STATE STREET SPDR S&P 500 ETF", currency: "USD", kind: "etf",
  listedOn: null, firstTradedOn: "1993-01-29",
};
const APPLE: LocalStockResult = {
  ...SPY, listingId: 5002, market: "NASDAQ", symbol: "AAPL", code: "AAPL", name: "애플",
  nameEn: "APPLE INC", kind: "stock", firstTradedOn: null,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

async function optionsFor(results: LocalStockResult[]) {
  routeGet({
    local: () => Promise.resolve(local(results)),
    external: () => Promise.resolve(external([{ market: "TSE", symbol: "7203.T", name: "Toyota Motor Corporation",
      currency: "JPY", kind: "stock", firstTradedOn: "1999-05-06" }])),
  });
  render(<StockSearch value={null} onSelect={vi.fn()} />);
  await userEvent.type(screen.getByRole("searchbox"), "s");
  return screen.findAllByRole("option");
}

const lineOf = (options: HTMLElement[], text: string) => {
  const found = options.find((o) => (o.textContent ?? "").includes(text));
  if (found === undefined) throw new Error(`줄이 없다: ${text}`);
  return found.textContent ?? "";
};

describe("주식 검색 결과 줄의 상장일", () => {
  it("국내는 키움 상장일 — 상장 …", async () => {
    const options = await optionsFor([{ ...SAMSUNG, firstTradedOn: "2000-01-04" }]);
    const line = lineOf(options, "삼성전자(005930)");
    expect(line).toContain("상장 1975-06-11");
    expect(line).not.toContain("첫 거래");
  });

  it("키움 상장일이 없으면 저장된 첫 거래일 — 첫 거래 …", async () => {
    const options = await optionsFor([SPY]);
    const line = lineOf(options, "(SPY)");
    expect(line).toContain("첫 거래 1993-01-29");
    expect(line).not.toContain("상장 ");
  });

  it("둘 다 없으면 그 글자를 뺀다 — 줄은 그대로", async () => {
    const options = await optionsFor([APPLE]);
    const line = lineOf(options, "(AAPL)");
    expect(line).not.toMatch(/상장 \d|첫 거래 \d/);
    expect(line).toContain("NASDAQ · USD");
  });

  it("014 전 응답(firstTradedOn 칸 없음)도 그대로 그린다", async () => {
    // `SAMSUNG` 픽스처(006)가 014 전 꼴이다 — `firstTradedOn` 칸이 없다.
    expect("firstTradedOn" in SAMSUNG).toBe(false);
    const options = await optionsFor([SAMSUNG]);
    expect(lineOf(options, "삼성전자(005930)")).toContain("상장 1975-06-11");
  });

  it("일본 외부 결과도 저장된 첫 거래일이다", async () => {
    await optionsFor([SAMSUNG]);
    await screen.findByText(/Toyota Motor Corporation/);
    expect(lineOf(screen.getAllByRole("option"), "(7203)")).toContain("첫 거래 1999-05-06");
  });

  it("기준 설명이 마우스를 올리면 보인다", async () => {
    await optionsFor([SPY]);
    expect(screen.getByTitle(/시세 출처\(Yahoo\)가 시세를 가진 첫 날/)).toBeInTheDocument();
  });
});
