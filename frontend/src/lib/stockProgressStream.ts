/**
 * 주식 수집 진행 구독 (T095) — 005 FR-047, contracts/rest-api.
 *
 * 003이 FX에서 만든 구독과 같은 모양이다. **`error`에서 `close()`하지 않는다** —
 * `EventSource`의 자동 재연결에 의존하는 것이 SSE를 택한 근거이며, 닫으면 그 동작을
 * 없애게 된다 (003이 001에서 얻은 교훈).
 *
 * 수집이 끝나면 `completed`가 온다. 화면은 그 신호를 받아 시뮬레이션을 다시 요청한다 —
 * 부분 결과를 먼저 보여주지 않는 대신(FR-049) 완료 시점은 알려야 한다.
 */

/** 상대 경로 기본값 — `next.config.ts`의 rewrite로 동일 출처를 유지한다. */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface StockProgressSnapshot {
  jobId: number;
  chunksDone: number;
  chunksTotal: number;
  rangeStart: string;
  rangeEnd: string;
}

export interface StockProgressHandlers {
  onSnapshot: (snapshot: StockProgressSnapshot) => void;
  onCompleted: () => void;
  onFailed: (reason: string) => void;
}

export function subscribeStockProgress(
  jobId: number,
  handlers: StockProgressHandlers,
): () => void {
  const source = new EventSource(`${BASE_URL}/api/stocks/progress?jobId=${jobId}`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<StockProgressSnapshot>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });

  source.addEventListener("completed", () => {
    handlers.onCompleted();
    // 완료는 더 받을 것이 없는 상태다. 여기서는 닫아야 재연결이 반복되지 않는다.
    source.close();
  });

  source.addEventListener("failed", (e) => {
    const body = parse<{ reason?: string }>((e as MessageEvent<string>).data);
    handlers.onFailed(body?.reason ?? "수집에 실패했습니다.");
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
  });

  return () => source.close();
}
