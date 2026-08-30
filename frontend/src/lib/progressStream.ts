/**
 * 진행률 SSE 구독 (T102) — contracts/sse-progress.md.
 *
 * 브라우저 `EventSource`의 **자동 재연결에 의존한다.** 수집이 수 분간 이어지므로
 * 연결 끊김 복구를 직접 구현하지 않는 것이 SSE를 택한 이유다 (research R4).
 */

import type { ProgressState } from "./types";

/**
 * 상대 경로 기본값 — `next.config.ts`의 rewrite로 동일 출처를 유지한다.
 * `EventSource`는 커스텀 헤더를 붙일 수 없어 CORS 우회가 특히 번거롭다.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface ProgressHandlers {
  onProgress: (state: ProgressState) => void;
  onCompleted: (state: ProgressState) => void;
  onError?: (message: string) => void;
}

/** 구독을 시작하고 해제 함수를 돌려준다. */
export function subscribeProgress(jobId: number, handlers: ProgressHandlers): () => void {
  const source = new EventSource(`${BASE_URL}/api/fx/progress?jobId=${jobId}`);

  const parse = (raw: string): ProgressState | null => {
    try {
      return JSON.parse(raw) as ProgressState;
    } catch {
      return null;
    }
  };

  source.addEventListener("progress", (e) => {
    const state = parse((e as MessageEvent<string>).data);
    if (state) handlers.onProgress(state);
  });

  source.addEventListener("completed", (e) => {
    const state = parse((e as MessageEvent<string>).data);
    if (state) handlers.onCompleted(state);
    // 종료 이벤트를 받으면 재연결하지 않는다
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
    handlers.onError?.("진행률 연결이 끊겼습니다. 자동으로 다시 연결합니다.");
  });

  return () => source.close();
}
