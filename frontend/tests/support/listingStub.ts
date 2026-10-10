/**
 * 고른 대상의 상장일 경로 대역 (014 반복 2026-10-10g T169) — contracts A11. `tests/setup.ts`가 `fetch`에 건다(이력·저장한 비교 대역 곁).
 *
 * 주식·가상자산 메뉴의 고른 줄은 대상이 있으면 이 경로를 묻는다. 상장일이 주제가 아닌 화면 테스트는 `listing: null`(모름)을 본다 — 요청이
 * 대역 없이 나가면 테스트가 네트워크를 부른다(헌법 원칙 III). 상장일 테스트는 아래 도우미로 심고, 붙잡고, 실패를 만든다.
 *
 * 서버를 흉내 내는 범위: 주식은 `market`·`symbol`, 코인은 `coinId`로 찾는다. 심지 않은 대상은 `listing: null`이다(404를 흉내 내지 않는다).
 */
import type { ListingDate } from "@/lib/types";

const STOCK = "/api/stocks/listing-date";
const COIN = "/api/crypto/listing-date";

let answers = new Map<string, ListingDate | null>();
let failing = false;
let holding = false;
let held: Array<() => void> = [];
const calls: string[] = [];

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const stockKey = (market: string, symbol: string) => `stock:${market}:${symbol}`;
const coinKey = (coinId: number | string) => `coin:${coinId}`;

/** `fetch`의 상장일 경로 요청에 답한다. 다른 경로면 `null`이다. */
export async function handleListing(input: RequestInfo | URL): Promise<Response | null> {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const url = new URL(raw, "http://test");
  let key: string;
  let ident: Record<string, unknown>;
  if (url.pathname === STOCK) {
    const market = url.searchParams.get("market") ?? "";
    const symbol = url.searchParams.get("symbol") ?? "";
    key = stockKey(market, symbol);
    ident = { market, symbol };
  } else if (url.pathname === COIN) {
    const coinId = url.searchParams.get("coinId") ?? "";
    key = coinKey(coinId);
    ident = { coinId: Number(coinId) };
  } else {
    return null;
  }
  calls.push(url.pathname + url.search);
  if (holding) await new Promise<void>((resolve) => held.push(resolve));
  if (failing) return json(500, { status: "internal", message: "대역이 실패를 만들었다" });
  return json(200, { ...ident, listing: answers.get(key) ?? null });
}

export function resetListingStub(): void {
  answers = new Map();
  failing = false;
  holding = false;
  held = [];
  calls.length = 0;
}

export const listingStub = {
  seedStock(market: string, symbol: string, listing: ListingDate | null): void {
    answers.set(stockKey(market, symbol), listing);
  },
  seedCoin(coinId: number, listing: ListingDate | null): void {
    answers.set(coinKey(coinId), listing);
  },
  /** 이후 요청을 500으로 답한다. */
  fail(): void {
    failing = true;
  },
  /** 이후 요청의 답을 붙잡는다 — `release`가 붙잡은 차례로 놓는다. */
  hold(): void {
    holding = true;
  },
  /** 붙잡은 답을 차례(`order` — 붙잡은 차례의 번호)로 놓고, 붙잡기를 그친다. */
  release(order?: number[]): void {
    holding = false;
    const waiting = held;
    held = [];
    for (const i of order ?? waiting.map((_, n) => n)) waiting[i]?.();
  },
  held(): number {
    return held.length;
  },
  calls(): string[] {
    return [...calls];
  },
};
