/**
 * 코인 목록 갱신 진행 구독 (T020) — 007 FR-005b, contracts/rest-api `GET /api/crypto/list/progress`, analyze C2.
 *
 * 처음 받는 목록은 약 2분 걸린다. 진행이 보이지 않으면 사용자는 멈춘 것으로 읽는다(헌법 원칙 VII). 005의 수집 진행
 * 구독과 같은 모양이다 — **`error`에서 `close()`하지 않는다.** `EventSource`의 자동 재연결에 의존하는 것이 SSE를 택한
 * 근거다.
 *
 * 갱신 중이 아니면 서버가 마지막 상태(`completed`·`failed`·`idle`)를 한 번 보내고 닫는다.
 */
import type { CoinListProgress, CoinListReason } from "@/lib/types";

/** 상대 경로 기본값 — `next.config.ts`의 rewrite로 동일 출처를 유지한다. */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface CoinListProgressHandlers {
  onSnapshot: (progress: CoinListProgress) => void;
  /** 갱신이 끝났다(또는 갱신 중이 아니었다). 화면은 검색을 다시 보낸다. */
  onCompleted: () => void;
  onFailed: (reason: CoinListReason, message: string) => void;
}

export function subscribeCoinListProgress(handlers: CoinListProgressHandlers): () => void {
  const source = new EventSource(`${BASE_URL}/api/crypto/list/progress`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const progress = parse<CoinListProgress>((e as MessageEvent<string>).data);
    if (progress) handlers.onSnapshot(progress);
  });

  const finish = () => {
    handlers.onCompleted();
    // 끝난 상태다. 닫지 않으면 서버가 닫은 스트림에 다시 붙어 같은 사건을 되풀이한다.
    source.close();
  };
  source.addEventListener("completed", finish);
  source.addEventListener("idle", finish);

  source.addEventListener("failed", (e) => {
    const body = parse<{ reason?: CoinListReason; message?: string }>(
      (e as MessageEvent<string>).data);
    handlers.onFailed(body?.reason ?? "network", body?.message ?? "");
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
  });

  return () => source.close();
}
