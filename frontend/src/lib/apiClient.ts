/**
 * 백엔드 API 클라이언트 (T027).
 *
 * 금액·비율은 **문자열로 수신하고 문자열로 유지한다.** JSON `number`는 IEEE 754
 * 배정밀도라 `Decimal` 정밀도가 손실되며, 이는 헌법 원칙 VI를 API 경계에서 무력화한다.
 */

/**
 * 기본값은 **빈 문자열(상대 경로)**이다. `next.config.ts`의 rewrite가 `/api/fx/*`를
 * 백엔드로 프록시하므로 동일 출처가 되어 CORS가 필요 없다.
 *
 * 프록시를 우회해 백엔드를 직접 가리켜야 할 때만 `NEXT_PUBLIC_API_BASE_URL`을 준다.
 * 그 경우 백엔드에 CORS 설정이 따로 필요하다.
 */
const BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

/** 서버가 문자열로 내려주는 십진 값. `number`로 변환하지 않는다. */
export type DecimalString = string;

export type CurrencyCode = "USD" | "JPY" | "EUR";

export interface ApiErrorBody {
  status: string;
  message: string;
}

export class ApiError extends Error {
  constructor(
    readonly httpStatus: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
  });

  if (!res.ok) {
    let body: ApiErrorBody | null = null;
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      // 본문이 JSON이 아니면 상태 코드만으로 오류를 구성한다
    }
    throw new ApiError(res.status, body?.status ?? "unknown", body?.message ?? res.statusText);
  }

  return (await res.json()) as T;
}

export const apiClient = {
  get: <T>(path: string) => request<T>(path),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
};
