/**
 * `/api/history` 대역 (012 T043) — research R12-12. `tests/setup.ts`가 `fetch`에 건다.
 *
 * 이력이 주제가 아닌 화면·스토어 테스트는 빈 이력과 성공하는 저장을 본다 — 시뮬레이션 응답을 모의하는 테스트(`apiClient.get` 모의)가 이력 요청까지
 * 가로채지 않는다. 이력 테스트는 아래 도우미로 심고, 읽고, 실패를 만든다.
 *
 * 서버를 흉내 내는 범위:
 * - 식별자는 서버 규칙(= 012 전 화면 lib 규칙)과 같다. **옮기기로 받은 항목에 `id`가 있으면 그것을 쓴다** — 옛 키에 `id`를 넣어 둔 기존 화면 테스트가
 *   그 `id`로 항목을 찾는다(analyze T1). 서버 규칙과의 일치는 백엔드 T039가 따로 확인한다
 * - 차례는 마지막 실행 내림차순이다. 시각은 부를 때마다 1초씩 늘어난다(같은 시각이 없다)
 * - 옮기기는 `start`가 없는 항목을 건너뛴다(`skipped`) — 서버의 검증 실패를 흉내 낸다
 */

type Asset = "stock" | "crypto" | "deposit" | "realestate";
type Entry = Record<string, unknown> & { id: string; lastRunAt: string };

const BASE = Date.parse("2026-10-06T00:00:00Z");
let tick = 0;
const now = (): string => new Date(BASE + 1000 * tick++).toISOString().replace(".000Z", "Z");

const store = new Map<Asset, Map<string, Entry>>();
let retentionDays: number | null = 30;
let failures: Array<{ method: string; path: RegExp }> = [];
const calls: Array<{ method: string; path: string; body: unknown }> = [];

function bucket(asset: Asset): Map<string, Entry> {
  let found = store.get(asset);
  if (found === undefined) {
    found = new Map();
    store.set(asset, found);
  }
  return found;
}

/** 서버(`history_conditions`)와 같은 식별자 규칙. */
export function stubId(asset: Asset, c: Record<string, unknown>): string {
  const recurring = c.mode === "recurring" ? `|recurring:${(c.frequency as string | undefined) ?? "monthly"}` : "";
  if (asset === "stock") {
    const s = c.stock as Record<string, unknown>;
    return [s.market, s.symbol, c.start, c.principal, c.principalCurrency, c.reinvest ? "R" : "N"].join("|") + recurring;
  }
  if (asset === "crypto") {
    const coin = c.coin as Record<string, unknown>;
    return [coin.coinId, c.start, c.principal, c.principalCurrency].join("|") + recurring;
  }
  if (asset === "deposit") {
    return [c.institution, c.start, c.principal].join("|") + (c.product === "installment" ? "|installment" : "");
  }
  return [c.complexId, c.area, c.buyDate, c.buyPrice ?? "market"].join("|");
}

/** 조건 칸만 남긴다 — 결과·`id`·`savedAt`·`lastRunAt`을 버린다. */
function conditionOf(raw: Record<string, unknown>): Record<string, unknown> {
  const out = { ...raw };
  delete out.id;
  delete out.savedAt;
  delete out.lastRunAt;
  return out;
}

function listBody(asset: Asset): { entries: Entry[]; retentionDays: number | null } {
  const entries = [...bucket(asset).values()].sort((a, b) => b.lastRunAt.localeCompare(a.lastRunAt));
  return { entries, retentionDays };
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** `fetch`의 `/api/history` 요청에 답한다. 다른 경로면 `null`이다. */
export async function handleHistory(input: RequestInfo | URL, init?: RequestInit): Promise<Response | null> {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const url = new URL(raw, "http://test");
  if (!url.pathname.startsWith("/api/history")) return null;
  const method = (init?.method ?? "GET").toUpperCase();
  const body: unknown = init?.body ? JSON.parse(String(init.body)) : undefined;
  calls.push({ method, path: url.pathname + url.search, body });
  if (failures.some((f) => f.method === method && f.path.test(url.pathname))) {
    return json(500, { status: "internal", message: "대역이 실패를 만들었다" });
  }
  if (url.pathname === "/api/history/settings") {
    if (method === "PUT") retentionDays = (body as { retentionDays: number | null }).retentionDays;
    return json(200, { retentionDays, isDefault: retentionDays === 30, options: [7, 30, 90, 180, 365, null] });
  }
  const [, , , assetRaw, sub] = url.pathname.split("/");
  const asset = assetRaw as Asset;
  if (method === "GET") return json(200, listBody(asset));
  if (method === "PUT") {
    const condition = conditionOf((body as { condition: Record<string, unknown> }).condition);
    const id = stubId(asset, condition);
    bucket(asset).set(id, { ...condition, id, lastRunAt: now() });
    return json(200, listBody(asset));
  }
  if (method === "DELETE") {
    bucket(asset).delete(url.searchParams.get("id") ?? "");
    return json(200, listBody(asset));
  }
  if (method === "POST" && sub === "import") {
    let imported = 0;
    let merged = 0;
    let skipped = 0;
    for (const item of (body as { entries: Array<Record<string, unknown>> }).entries) {
      if (typeof item.start !== "string" && typeof item.buyDate !== "string") {
        skipped += 1;
        continue;
      }
      const condition = conditionOf(item);
      const id = typeof item.id === "string" ? item.id : stubId(asset, condition);
      const lastRunAt = typeof item.savedAt === "string" ? item.savedAt.replace(".000Z", "Z") : now();
      const existing = bucket(asset).get(id);
      if (existing !== undefined) merged += 1;
      else imported += 1;
      const later = existing !== undefined && existing.lastRunAt > lastRunAt ? existing.lastRunAt : lastRunAt;
      bucket(asset).set(id, { ...condition, id, lastRunAt: later });
    }
    return json(200, { imported, merged, skipped, ...listBody(asset) });
  }
  return json(404, { status: "unknown", message: `대역에 없는 경로: ${method} ${url.pathname}` });
}

/** 테스트마다 비운다(`tests/setup.ts`의 `beforeEach`). */
export function resetHistoryStub(): void {
  store.clear();
  retentionDays = 30;
  failures = [];
  calls.length = 0;
  tick = 0;
}

export const historyStub = {
  /** 서버에 있는 것처럼 심는다. `lastRunAt`이 없으면 지금 시각이다. */
  seed(asset: Asset, entries: ReadonlyArray<object>): void {
    for (const entry of entries as ReadonlyArray<Record<string, unknown>>) {
      const condition = conditionOf(entry);
      const id = typeof entry.id === "string" ? entry.id : stubId(asset, condition);
      bucket(asset).set(id, { ...condition, id, lastRunAt: (entry.lastRunAt as string | undefined) ?? now() });
    }
  },
  entries(asset: Asset): Entry[] {
    return listBody(asset).entries;
  },
  /** 그 방법·경로의 요청을 500으로 만든다. `heal()`로 되돌린다. */
  fail(method: string, path: RegExp = /^\/api\/history/): void {
    failures.push({ method: method.toUpperCase(), path });
  },
  heal(): void {
    failures = [];
  },
  calls(): ReadonlyArray<{ method: string; path: string; body: unknown }> {
    return calls;
  },
  setRetention(days: number | null): void {
    retentionDays = days;
  },
};
