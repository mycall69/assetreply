/**
 * `/api/comparison/settings` 대역 (014 반복 2026-10-13 T214) — contracts A18. `tests/setup.ts`가 `fetch`에 건다(이력·저장한 비교·상장일 대역 곁).
 *
 * 투자 비교 화면은 열 때마다 이 경로를 묻고, 설정 화면의 "투자 비교" 절도 이 경로를 읽고 쓴다. 설정이 주제가 아닌 화면 테스트는 기본(최대 20개)을
 * 본다 — 요청이 대역 없이 나가면 테스트가 네트워크를 부른다(헌법 원칙 III). 설정 테스트는 아래 도우미로 심고, 붙잡고, 실패를 만든다.
 *
 * 서버를 흉내 내는 범위: `PUT`은 JSON 정수 2~100만 저장한다(불리언·소수·글자는 422 `invalid_setting`) — 서버의 메시지와 같은 글자다.
 */

const PATH = "/api/comparison/settings";
const DEFAULT = 20;

let current: number | null = null;
let failures: string[] = [];
let holding = false;
let held: Array<() => void> = [];
const calls: Array<{ method: string; body: unknown }> = [];

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const settings = () => ({ maxTargets: current ?? DEFAULT, defaultMaxTargets: DEFAULT, minTargets: 2, limitTargets: 100 });

function answer(method: string, body: unknown): Response {
  if (failures.includes(method)) return json(500, { status: "internal", message: "대역이 실패를 만들었다" });
  if (method === "GET") return json(200, settings());
  if (method === "PUT") {
    const value = (body as { maxTargets?: unknown } | null)?.maxTargets;
    if (typeof value !== "number" || !Number.isInteger(value) || value < 2 || value > 100) {
      return json(422, { status: "invalid_setting", message: `최대 대상 수는 2~100 사이의 정수여야 합니다: ${JSON.stringify(value)}` });
    }
    current = value;
    return json(200, settings());
  }
  return json(404, { status: "unknown", message: `대역에 없는 경로: ${method} ${PATH}` });
}

/** `fetch`의 설정 경로 요청에 답한다. 다른 경로면 `null`이다. */
export async function handleCompareSettings(input: RequestInfo | URL, init?: RequestInit): Promise<Response | null> {
  const raw = typeof input === "string" ? input : input instanceof URL ? input.toString() : input.url;
  const url = new URL(raw, "http://test");
  if (url.pathname !== PATH) return null;
  const method = (init?.method ?? "GET").toUpperCase();
  const body: unknown = init?.body ? JSON.parse(String(init.body)) : undefined;
  calls.push({ method, body });
  if (holding) await new Promise<void>((resolve) => held.push(resolve));
  return answer(method, body);
}

/** 테스트마다 비운다(`tests/setup.ts`의 `beforeEach`). */
export function resetCompareSettingsStub(): void {
  current = null;
  failures = [];
  holding = false;
  held = [];
  calls.length = 0;
}

export const compareSettingsStub = {
  /** 서버에 저장된 최대 대상 수를 심는다. */
  set(value: number): void {
    current = value;
  },
  stored(): number | null {
    return current;
  },
  /** 그 방법의 요청을 500으로 만든다. */
  fail(method: string): void {
    failures.push(method.toUpperCase());
  },
  heal(): void {
    failures = [];
  },
  /** 답을 붙잡는다 — `release()`까지 응답하지 않는다. */
  hold(): void {
    holding = true;
  },
  release(): void {
    holding = false;
    for (const resolve of held.splice(0)) resolve();
  },
  calls(): ReadonlyArray<{ method: string; body: unknown }> {
    return calls;
  },
};
