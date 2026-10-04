/**
 * 가상자산 수집 진행 구독 (T033) — 007 FR-013, FR-020, contracts/rest-api `GET /api/crypto/progress`.
 *
 * 005의 주식 진행 구독과 같은 모양이다. **`error`에서 `close()`하지 않는다** — `EventSource`의 자동 재연결에 의존하는 것이 SSE를
 * 택한 근거다. 실패는 종류(`kind`)를 함께 넘긴다 — 화면이 종류마다 다른 말을 한다(FR-020).
 */
import type { CryptoFailureKind } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface CryptoProgressSnapshot {
  jobId: number;
  status: string;
  chunksDone: number;
  chunksTotal: number;
  /** 작업 구간 가운데 이미 받은 날(달력 일수). */
  daysDone: number;
  daysTotal: number;
  missingFrom: string;
  missingThrough: string;
}

export interface CryptoProgressHandlers {
  onSnapshot: (snapshot: CryptoProgressSnapshot) => void;
  onCompleted: () => void;
  onFailed: (kind: CryptoFailureKind | null, reason: string) => void;
}

export function subscribeCryptoProgress(
  jobId: number,
  handlers: CryptoProgressHandlers,
): () => void {
  const source = new EventSource(`${BASE_URL}/api/crypto/progress?jobId=${jobId}`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<CryptoProgressSnapshot>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });

  source.addEventListener("completed", () => {
    handlers.onCompleted();
    // 완료는 더 받을 것이 없는 상태다. 닫아야 재연결이 반복되지 않는다.
    source.close();
  });

  source.addEventListener("failed", (e) => {
    const body = parse<{ kind?: CryptoFailureKind | null; reason?: string }>(
      (e as MessageEvent<string>).data);
    handlers.onFailed(body?.kind ?? null, body?.reason ?? "수집에 실패했습니다.");
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
  });

  return () => source.close();
}
