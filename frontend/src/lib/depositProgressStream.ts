/**
 * 예금 금리 수집 진행 구독 (T021) — 008 FR-011, FR-016, contracts/rest-api `GET /api/deposit/progress`.
 *
 * 007의 진행 구독과 같은 모양이다. 진행은 **받은 달 / 받을 달**이다. **`error`에서 `close()`하지 않는다** — `EventSource`의
 * 자동 재연결에 의존하는 것이 SSE를 택한 근거다. 실패는 종류(`kind`)를 함께 넘긴다 — 화면이 종류마다 다른 말을 한다(FR-016).
 */
import type { DepositFailureKind } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface DepositProgressSnapshot {
  jobId: number;
  status: string;
  institution: string;
  /** 필요한 구간 가운데 받은 구간 안의 달. 미발표 달은 받지 못해 끝까지 받을 달보다 적을 수 있다. */
  monthsDone: number;
  /** 필요한 구간(시작 달 ~ 이번 달)의 달 수 — 처음 받을 때도 안다. */
  monthsTotal: number;
  missingFrom: string;
  missingThrough: string;
}

export interface DepositProgressHandlers {
  onSnapshot: (snapshot: DepositProgressSnapshot) => void;
  onCompleted: () => void;
  onFailed: (kind: DepositFailureKind | null, reason: string) => void;
}

export function subscribeDepositProgress(
  jobId: number,
  handlers: DepositProgressHandlers,
): () => void {
  const source = new EventSource(`${BASE_URL}/api/deposit/progress?jobId=${jobId}`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<DepositProgressSnapshot>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });

  source.addEventListener("completed", () => {
    handlers.onCompleted();
    // 완료는 더 받을 것이 없는 상태다. 닫아야 재연결이 반복되지 않는다.
    source.close();
  });

  source.addEventListener("failed", (e) => {
    const body = parse<{ kind?: DepositFailureKind | null; reason?: string }>(
      (e as MessageEvent<string>).data);
    handlers.onFailed(body?.kind ?? null, body?.reason ?? "수집에 실패했습니다.");
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
  });

  return () => source.close();
}
