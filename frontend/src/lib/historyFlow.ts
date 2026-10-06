/**
 * 네 스토어가 함께 쓰는 이력 흐름 (012 T056) — FR-011, FR-013, FR-014, FR-014a, data-model 5.2, research R12-11.
 *
 * 이력은 로컬 DB에 있다(012 전에는 브라우저 저장소). 스토어마다 항목 모양·다시 실행·비교는 다르지만 불러오기·옮기기·저장·삭제와 그 실패 문구는 같다 —
 * 한 곳에 두지 않으면 한 자산군만 실패를 조용히 삼키는 일이 생긴다.
 *
 * - 불러오기: 그 자산군의 옛 키 → 옮기기 → 2xx면 그 키 삭제 → 목록. 옮기기·목록이 실패하면 `historyLoadError`다 — 빈 목록으로 보이면 사용자는 이력이
 *   지워졌다고 오해한다(FR-014a). 키는 남아 다시 시도가 같은 차례를 한다
 * - 저장·삭제: 응답의 목록으로 바꾼다. 실패해도 결과는 그대로이고 알린다(FR-014 — 조용히 실패하지 않는다)
 * - 목록을 받을 때마다 선택을 목록에 있는 항목으로 줄인다. 이미 받은 비교는 건드리지 않는다(spec Edge Cases — 비교에 쓰인 항목이 기간 지나 지워짐)
 */

import { deleteHistory, fetchHistory, importHistory, putHistory, type HistoryAsset, type HistoryList } from "@/lib/historyApi";
import { clearLegacy, readLegacy } from "@/lib/legacyHistory";

export const HISTORY_LOAD_ERROR = "이력을 불러오지 못했습니다.";
export const HISTORY_SAVE_ERROR = "이력을 저장하지 못했습니다. 결과는 그대로이고, 다시 실행하면 다시 저장합니다.";
export const HISTORY_REMOVE_ERROR = "이력을 지우지 못했습니다.";

export interface HistorySlice<E extends { id: string }> {
  history: E[];
  /** 첫 목록이 오기 전 — 빈 상태 문구를 숨긴다. */
  historyLoading: boolean;
  /** 옮기기·목록 실패(FR-014a). */
  historyLoadError: string | null;
  /** 저장·삭제 실패(FR-014). */
  historySaveError: string | null;
  /** 옮기지 못한 항목 수 알림. */
  historyNotice: string | null;
  /** 목록 응답의 보관 기간. `null`은 무기한, `undefined`는 아직 모른다(안내가 기간을 말하지 않는다). */
  retentionDays: number | null | undefined;
  selectedHistory: string[];
}

export const INITIAL_HISTORY = {
  history: [],
  historyLoading: true,
  historyLoadError: null,
  historySaveError: null,
  historyNotice: null,
  retentionDays: undefined,
  selectedHistory: [],
} satisfies HistorySlice<{ id: string }>;

type Get<E extends { id: string }> = () => HistorySlice<E>;
type Set<E extends { id: string }> = (partial: Partial<HistorySlice<E>>) => void;

function applied<E extends { id: string }>(list: HistoryList<E>, selected: string[]): Partial<HistorySlice<E>> {
  const ids = new Set(list.entries.map((e) => e.id));
  return {
    history: list.entries, retentionDays: list.retentionDays, historyLoading: false, historyLoadError: null,
    selectedHistory: selected.filter((id) => ids.has(id)),
  };
}

/** 같은 자산군의 불러오기가 겹치면 하나로 합친다 — 개발 모드의 이중 마운트가 옛 키를 두 번 옮기지 않게 한다. */
const inflight = new Map<HistoryAsset, Promise<void>>();

export function restoreHistoryFlow<E extends { id: string }>(asset: HistoryAsset, get: Get<E>, set: Set<E>): Promise<void> {
  const running = inflight.get(asset);
  if (running !== undefined) return running;
  const task = (async () => {
    set({ historyLoading: true, historyLoadError: null });
    try {
      const legacy = readLegacy(asset);
      let notice = get().historyNotice;
      // 읽을 수 없는 키는 옮기지도 지우지도 않는다 — 지우면 사용자가 되살릴 길이 없다.
      if (legacy.status === "entries") {
        const result = await importHistory<E>(asset, legacy.entries);
        clearLegacy(asset);
        if (result.skipped > 0) notice = `읽을 수 없는 브라우저 이력 ${result.skipped}개는 옮기지 못했습니다.`;
      }
      const list = await fetchHistory<E>(asset);
      set({ ...applied(list, get().selectedHistory), historyNotice: notice });
    } catch {
      set({ historyLoading: false, historyLoadError: HISTORY_LOAD_ERROR });
    }
  })().finally(() => inflight.delete(asset));
  inflight.set(asset, task);
  return task;
}

/** 실행한 조건을 남긴다. 조건만 보낸다 — 결과·`id`·시각은 싣지 않는다(005 R5-9). 던지지 않는다. */
export async function saveHistoryFlow<E extends { id: string }>(
  asset: HistoryAsset, condition: object, get: Get<E>, set: Set<E>,
): Promise<void> {
  try {
    const list = await putHistory<E>(asset, condition);
    set({ ...applied(list, get().selectedHistory), historySaveError: null });
  } catch {
    set({ historySaveError: HISTORY_SAVE_ERROR });
  }
}

/** 항목을 지운다. 지웠으면 참이다 — 스토어가 그 항목의 비교 선을 함께 내린다. 던지지 않는다. */
export async function removeHistoryFlow<E extends { id: string }>(
  asset: HistoryAsset, id: string, get: Get<E>, set: Set<E>,
): Promise<boolean> {
  try {
    const list = await deleteHistory<E>(asset, id);
    set({ ...applied(list, get().selectedHistory), historySaveError: null });
    return true;
  } catch {
    set({ historySaveError: HISTORY_REMOVE_ERROR });
    return false;
  }
}
