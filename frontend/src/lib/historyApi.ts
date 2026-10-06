/**
 * 시뮬레이션 이력 경로 (012 T055) — contracts/rest-api.md 2~6, research R12-12.
 *
 * 공통 요청 함수(`request`)를 직접 쓴다 — `apiClient.get` 등을 거치지 않는다. 이력은 시뮬레이션과 실패 영역이 다르다: 이력 요청이 실패해도 결과는
 * 보여야 하고(FR-014), 시뮬레이션 응답을 모의하는 테스트가 이력 요청까지 가로채면 이력과 무관한 단언이 흔들린다. 오류 모양(`ApiError`)은 같다.
 */

import { request } from "@/lib/apiClient";

export type HistoryAsset = "stock" | "crypto" | "deposit" | "realestate";

/** 목록 — 마지막 실행 내림차순. `retentionDays`가 `null`이면 무기한이다. */
export interface HistoryList<E> {
  entries: E[];
  retentionDays: number | null;
}

export interface ImportResult<E> extends HistoryList<E> {
  imported: number;
  merged: number;
  /** 서버가 읽지 못해 건너뛴 항목 수 — 0보다 크면 화면이 알린다(조용히 버리지 않는다). */
  skipped: number;
}

export interface RetentionSetting {
  retentionDays: number | null;
  isDefault: boolean;
  options: Array<number | null>;
}

const json = (body: unknown) => JSON.stringify(body);

export const fetchHistory = <E>(asset: HistoryAsset) => request<HistoryList<E>>(`/api/history/${asset}`);

/** 실행한 조건을 저장한다 — 같은 조건이면 맨 앞으로 오고 마지막 실행 시각이 바뀐다. 결과는 싣지 않는다(005 R5-9). */
export const putHistory = <E>(asset: HistoryAsset, condition: object) =>
  request<HistoryList<E>>(`/api/history/${asset}`, { method: "PUT", body: json({ condition }) });

/** 식별자에는 `|`·`:`가 있다 — 질의로 인코딩한다. */
export const deleteHistory = <E>(asset: HistoryAsset, id: string) =>
  request<HistoryList<E>>(`/api/history/${asset}?id=${encodeURIComponent(id)}`, { method: "DELETE" });

/** 브라우저 옛 이력을 옮긴다(012 FR-013). 항목은 옛 키의 것 그대로다 — 서버가 식별자를 다시 계산한다. */
export const importHistory = <E>(asset: HistoryAsset, entries: unknown[]) =>
  request<ImportResult<E>>(`/api/history/${asset}/import`, { method: "POST", body: json({ entries }) });

export const fetchRetention = () => request<RetentionSetting>("/api/history/settings");

/** 무기한은 `null`이다. 저장하면 서버가 모든 자산군의 기한 지난 항목을 곧바로 지운다(FR-012). */
export const saveRetention = (retentionDays: number | null) =>
  request<RetentionSetting>("/api/history/settings", { method: "PUT", body: json({ retentionDays }) });
