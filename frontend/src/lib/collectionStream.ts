/**
 * 수집 스트림 구독 (T043) — contracts/rest-api 3절.
 *
 * `EventSource`의 **자동 재연결에 의존한다.** 수집이 수 분간 이어지므로 연결 끊김
 * 복구를 직접 구현하지 않는 것이 SSE를 택한 근거다 (002 progressStream의 교훈).
 *
 * 통화를 전환하면 기존 연결을 닫고 새로 연다. **이전 연결의 뒤늦은 이벤트가 새 화면에
 * 반영되어서는 안 된다** (FR-028) — 이벤트에 실린 `currency`를 현재 선택과 대조해
 * 거르는 것은 구독자(스토어)의 책임이다.
 */

import type { CollectionEventRow, CurrencyCode, TimelineSnapshot } from "./types";

/**
 * 상대 경로 기본값 — `next.config.ts`의 rewrite로 동일 출처를 유지한다.
 * `EventSource`는 커스텀 헤더를 붙일 수 없어 CORS 우회가 특히 번거롭다.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface IdlePayload {
  currency: CurrencyCode;
  callsToday: number;
  busyWith: CurrencyCode | null;
}

export interface CollectionStreamHandlers {
  onSnapshot: (snapshot: TimelineSnapshot) => void;
  onIdle: (payload: IdlePayload) => void;
  onEvent: (event: CollectionEventRow) => void;
  onError?: (message: string) => void;
}

/** 구독을 시작하고 해제 함수를 돌려준다. */
export function subscribeCollection(
  currency: CurrencyCode,
  handlers: CollectionStreamHandlers,
): () => void {
  const source = new EventSource(
    `${BASE_URL}/api/fx/collection/stream?currency=${currency}`,
  );

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<TimelineSnapshot>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });

  source.addEventListener("idle", (e) => {
    const payload = parse<IdlePayload>((e as MessageEvent<string>).data);
    if (payload) handlers.onIdle(payload);
  });

  source.addEventListener("event", (e) => {
    const row = parse<CollectionEventRow>((e as MessageEvent<string>).data);
    if (row) handlers.onEvent(row);
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
    handlers.onError?.("수집 스트림 연결이 끊겼습니다. 자동으로 다시 연결합니다.");
  });

  return () => source.close();
}
