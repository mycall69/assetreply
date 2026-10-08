/**
 * `/api/comparison/saved` 대역 (013 T060) — contracts/rest-api.md 2~4. `tests/setup.ts`가 `fetch`에 건다(이력 대역 곁).
 *
 * 저장한 비교가 주제가 아닌 화면 테스트는 빈 목록과 성공하는 저장을 본다. 저장 테스트는 아래 도우미로 심고, 읽고, 실패를 만든다.
 *
 * 서버를 흉내 내는 범위:
 * - `POST`는 늘 새 항목이다(같은 조건·이름이어도) — `id`는 1부터 늘어난다
 * - 차례는 `savedAt` 내림차순, 같으면 `id` 내림차순이다. 시각은 저장할 때마다 1초씩 늘어난다
 * - 이름은 앞뒤 공백을 뺀다. 빈 이름은 422 `invalid_comparison`
 * - `DELETE`는 없는 `id`도 200이다
 */

interface Entry {
  id: number;
  name: string;
  asset: string;
  condition: Record<string, unknown>;
  savedAt: string;
}

const BASE = Date.parse("2026-10-08T00:00:00Z");
let tick = 0;
let nextId = 1;
const now = (): string => new Date(BASE + 1000 * tick++).toISOString().replace(".000Z", "Z");

let rows: Entry[] = [];
let failures: Array<{ method: string; path: RegExp }> = [];
const calls: Array<{ method: string; path: string; body: unknown }> = [];

const PREFIX = "/api/comparison/saved";

function list(): Entry[] {
  return [...rows].sort((a, b) => b.savedAt.localeCompare(a.savedAt) || b.id - a.id);
}

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

/** `fetch`의 `/api/comparison/saved` 요청에 답한다. 다른 경로면 `null`이다. */
export async function handleSavedComparisons(input: RequestInfo | URL, init?: RequestInit): Promise<Response | null> {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const url = new URL(raw, "http://test");
  if (!url.pathname.startsWith(PREFIX)) return null;
  const method = (init?.method ?? "GET").toUpperCase();
  const body: unknown = init?.body ? JSON.parse(String(init.body)) : undefined;
  calls.push({ method, path: url.pathname + url.search, body });
  if (failures.some((f) => f.method === method && f.path.test(url.pathname))) {
    return json(500, { status: "internal", message: "대역이 실패를 만들었다" });
  }
  if (method === "GET" && url.pathname === PREFIX) return json(200, { entries: list() });
  if (method === "POST" && url.pathname === PREFIX) {
    const { name, condition } = body as { name: unknown; condition: Record<string, unknown> };
    const trimmed = typeof name === "string" ? name.trim() : "";
    if (trimmed === "") return json(422, { status: "invalid_comparison", message: "name: 이름이 비었습니다" });
    const entry: Entry = { id: nextId++, name: trimmed, asset: String(condition.asset), condition, savedAt: now() };
    rows.push(entry);
    return json(201, { entry, entries: list() });
  }
  if (method === "DELETE") {
    const id = Number(url.pathname.slice(PREFIX.length + 1));
    rows = rows.filter((r) => r.id !== id);
    return json(200, { entries: list() });
  }
  return json(404, { status: "unknown", message: `대역에 없는 경로: ${method} ${url.pathname}` });
}

/** 테스트마다 비운다(`tests/setup.ts`의 `beforeEach`). */
export function resetSavedComparisonStub(): void {
  rows = [];
  failures = [];
  calls.length = 0;
  tick = 0;
  nextId = 1;
}

export const savedComparisonStub = {
  /** 서버에 있는 것처럼 심는다. `id`·`savedAt`이 없으면 새로 매긴다. */
  seed(entries: ReadonlyArray<Partial<Entry> & { name: string; condition: Record<string, unknown> }>): void {
    for (const e of entries) {
      rows.push({ id: e.id ?? nextId++, name: e.name, asset: e.asset ?? String(e.condition.asset), condition: e.condition,
        savedAt: e.savedAt ?? now() });
    }
  },
  entries(): Entry[] {
    return list();
  },
  /** 그 방법·경로의 요청을 500으로 만든다. `heal()`로 되돌린다. */
  fail(method: string, path: RegExp = /^\/api\/comparison\/saved/): void {
    failures.push({ method: method.toUpperCase(), path });
  },
  heal(): void {
    failures = [];
  },
  calls(): ReadonlyArray<{ method: string; path: string; body: unknown }> {
    return calls;
  },
};
