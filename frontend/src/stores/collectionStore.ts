/**
 * 수집 상태 Zustand 스토어 (T044, T088) — 헌법 원칙 VII.
 *
 * 선택 통화와 스트림 상태를 한 곳에서 관리한다. 003에서 화면이 **선택한 통화 하나**만
 * 보여주게 되면서, 전환 시 이전 통화의 값이 남지 않는 것이 핵심 요구가 됐다 (FR-028).
 *
 * 002의 오늘 환율 새로고침에서 같은 계열의 결함을 겪었다 — 통화를 바꿨는데 이전 통화의
 * 결과가 화면에 남는 문제다. 여기서는 두 겹으로 막는다.
 *
 *  1. 전환 즉시 상태를 비운다 (한 프레임도 이전 값이 남지 않는다)
 *  2. 도착한 이벤트의 `currency`를 현재 선택과 대조해 거른다 (뒤늦은 갱신 차단)
 */

import { create } from "zustand";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeCollection } from "@/lib/collectionStream";
import type {
  CollectionEventRow,
  CurrencyCode,
  EventsResponse,
  TimelineSnapshot,
} from "@/lib/types";

interface StartResponse {
  jobs: { currency: string; joinedExisting: boolean }[];
}

/** 화면에 한 번에 보여줄 최근 사건 수. 목록이 길어지면 읽기 어려워진다. */
const EVENT_WINDOW = 50;

interface CollectionState {
  currency: CurrencyCode;
  snapshot: TimelineSnapshot | null;
  events: CollectionEventRow[];
  eventsDropped: number;
  jobsKept: number;
  callsToday: number;
  busyWith: CurrencyCode | null;
  error: string | null;
  notice: string | null;
  unsubscribe: (() => void) | null;

  selectCurrency: (currency: CurrencyCode) => void;
  load: () => Promise<void>;
  startCollection: () => Promise<void>;
  watch: () => void;
  stopWatching: () => void;
}

const EMPTY = {
  snapshot: null,
  events: [] as CollectionEventRow[],
  eventsDropped: 0,
  callsToday: 0,
  busyWith: null,
  error: null,
  notice: null,
};

export const useCollectionStore = create<CollectionState>((set, get) => ({
  currency: "USD",
  jobsKept: 20,
  unsubscribe: null,
  ...EMPTY,

  selectCurrency: (currency) => {
    if (currency === get().currency) return;
    get().stopWatching();
    // **전환 즉시 비운다.** 새 통화의 응답이 도착할 때까지 이전 통화의 시간축·기록·
    // 경고가 남으면, 사용자가 지금 보는 값이 어느 통화의 것인지 알 수 없다 (FR-028).
    set({ currency, ...EMPTY });
    void get().load();
    get().watch();
  },

  load: async () => {
    const requested = get().currency;
    try {
      const [timeline, events] = await Promise.all([
        apiClient.get<TimelineSnapshot>(
          `/api/fx/collection/timeline?currency=${requested}`,
        ),
        apiClient.get<EventsResponse>(
          `/api/fx/collection/events?currency=${requested}&limit=${EVENT_WINDOW}`,
        ),
      ]);
      // 응답이 도착하는 사이 사용자가 통화를 바꿨을 수 있다. 그 경우 버린다.
      if (get().currency !== requested) return;
      set({
        snapshot: timeline,
        callsToday: timeline.callsToday,
        busyWith: timeline.busyWith,
        events: events.events,
        eventsDropped: events.eventsDropped,
        jobsKept: events.retention.jobsKept,
        error: null,
      });
    } catch (err) {
      if (get().currency !== requested) return;
      set({
        error:
          err instanceof ApiError ? err.message : "수집 현황을 불러오지 못했습니다.",
      });
    }
  },

  startCollection: async () => {
    const requested = get().currency;
    try {
      await apiClient.post<StartResponse>("/api/fx/collect", {
        currency: requested,
      });
      if (get().currency !== requested) return;
      set({ notice: null, error: null });
      await get().load();
    } catch (err) {
      if (get().currency !== requested) return;
      set({
        error:
          err instanceof ApiError ? err.message : "수집을 시작하지 못했습니다.",
      });
    }
  },

  watch: () => {
    get().stopWatching();
    const requested = get().currency;
    const unsubscribe = subscribeCollection(requested, {
      onSnapshot: (snapshot) => {
        // 뒤늦게 도착한 이전 통화의 갱신을 거른다 (FR-028).
        if (get().currency !== snapshot.currency) return;
        set({
          snapshot,
          callsToday: snapshot.callsToday,
          busyWith: snapshot.busyWith,
        });
      },
      onIdle: (payload) => {
        if (get().currency !== payload.currency) return;
        set({
          snapshot: null,
          callsToday: payload.callsToday,
          busyWith: payload.busyWith,
        });
      },
      onEvent: (event) => {
        if (get().currency !== event.currency) return;
        // 새 사건만 앞에 덧붙인다. 전체를 교체하면 읽던 위치가 사라진다.
        set({ events: [event, ...get().events].slice(0, EVENT_WINDOW) });
      },
      onError: (message) => set({ notice: message }),
    });
    set({ unsubscribe });
  },

  stopWatching: () => {
    get().unsubscribe?.();
    set({ unsubscribe: null });
  },
}));
