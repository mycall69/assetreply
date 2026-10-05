/**
 * 부동산 수집 진행 구독 (T026) — 009 FR-011, FR-014, contracts/rest-api `GET /api/realestate/progress`.
 *
 * 008의 진행 구독과 같은 모양이다. 작업은 셋이다 — 행정구역(`region`, 받은 쪽 / 쪽 수), 단지 기본 정보(`complex_details`, 받은 단지
 * / 단지 수), 실거래(`trade`, 받은 달 / 받을 달). 진행은 종류와 상관없이 `done`·`total`이다. **`error`에서 `close()`하지 않는다** —
 * `EventSource`의 자동 재연결에 의존하는 것이 SSE를 택한 근거다. 실패는 종류(`kind`)를 함께 넘긴다 — 화면이 종류마다 다른 말을
 * 한다(FR-014).
 */
import type { RealEstateFailureKind } from "@/lib/types";

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export interface RealEstateProgressSnapshot {
  jobId: number;
  kind: "region" | "complex_details" | "trade";
  /** 작업 대상 — 실거래는 시·군·구 코드(`11710`), 기본 정보는 법정동 코드, 행정구역은 `regions`. */
  target: string;
  status: string;
  done: number;
  total: number;
}

export interface RealEstateProgressHandlers {
  onSnapshot: (snapshot: RealEstateProgressSnapshot) => void;
  onCompleted: () => void;
  onFailed: (kind: RealEstateFailureKind | null, reason: string) => void;
}

export function subscribeRealEstateProgress(
  jobId: number,
  handlers: RealEstateProgressHandlers,
): () => void {
  const source = new EventSource(`${BASE_URL}/api/realestate/progress?jobId=${jobId}`);

  function parse<T>(raw: string): T | null {
    try {
      return JSON.parse(raw) as T;
    } catch {
      return null;
    }
  }

  source.addEventListener("snapshot", (e) => {
    const snapshot = parse<RealEstateProgressSnapshot>((e as MessageEvent<string>).data);
    if (snapshot) handlers.onSnapshot(snapshot);
  });

  source.addEventListener("completed", () => {
    handlers.onCompleted();
    // 완료는 더 받을 것이 없는 상태다. 닫아야 재연결이 반복되지 않는다.
    source.close();
  });

  source.addEventListener("failed", (e) => {
    const body = parse<{ kind?: RealEstateFailureKind | null; reason?: string }>(
      (e as MessageEvent<string>).data);
    handlers.onFailed(body?.kind ?? null, body?.reason ?? "수집에 실패했습니다.");
    source.close();
  });

  source.addEventListener("error", () => {
    // EventSource가 스스로 재연결한다. 여기서 close하면 그 동작을 없애게 된다.
  });

  return () => source.close();
}
