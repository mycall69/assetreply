/**
 * 지표 이력 수집 진행 구독 (014 T058) — FR-016, contracts A4.
 *
 * 주식·가상자산의 진행 구독과 같은 모양이다. **`error`에서 `close()`하지 않는다** — `EventSource`의 자동 재연결에 의존한다. 완료·실패는
 * 더 받을 것이 없는 상태라 닫는다.
 */
import type { IndicatorProgress } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface IndicatorProgressHandlers {
  onSnapshot: (snapshot: IndicatorProgress) => void;
  onCompleted: () => void;
  onFailed: (kind: string | null, message: string) => void;
}

export function subscribeIndicatorProgress(url: string, handlers: IndicatorProgressHandlers): () => void {
  const source = new EventSource(`${BASE_URL}${url}`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<IndicatorProgress>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });
  source.addEventListener("completed", () => {
    handlers.onCompleted();
    source.close();
  });
  source.addEventListener("failed", (e) => {
    const body = parse<{ kind?: string | null; message?: string }>((e as MessageEvent<string>).data);
    handlers.onFailed(body?.kind ?? null, body?.message ?? "이력을 받지 못했습니다.");
    source.close();
  });

  return () => source.close();
}
