"use client";

/**
 * 수집 현황 (T047, T072, T086) — contracts/ui-wireframes.md W1.
 *
 * **통화 선택기가 맨 위**에 온다. 아래 모든 내용이 선택에 종속되므로 그 방향이 배치로
 * 드러나야 한다 (FR-027).
 *
 * 선택기는 002의 `components/fx/CurrencyTabs`를 **옮기지 않고 그대로 임포트한다**.
 * 파일을 옮기면 002 화면의 임포트가 깨질 위험만 생기고 얻는 것이 없다 (research R3-11).
 */

import { useEffect } from "react";
import { CurrencyCard } from "@/components/collection/CurrencyCard";
import { EventList } from "@/components/collection/EventList";
import { IncompleteRecordNotice } from "@/components/collection/IncompleteRecordNotice";
import { RateLimitBanner } from "@/components/collection/RateLimitBanner";
import { CurrencyTabs } from "@/components/fx/CurrencyTabs";
import { useCollectionStore } from "@/stores/collectionStore";

/** 한도 소진은 기록에 `rate_limited` 사건으로 남는다 (FR-025). */
function useRateLimited(): boolean {
  const events = useCollectionStore((s) => s.events);
  return events.some((e) => e.kind === "rate_limited");
}

export default function CollectionPage() {
  const currency = useCollectionStore((s) => s.currency);
  const snapshot = useCollectionStore((s) => s.snapshot);
  const events = useCollectionStore((s) => s.events);
  const eventsDropped = useCollectionStore((s) => s.eventsDropped);
  const jobsKept = useCollectionStore((s) => s.jobsKept);
  const callsToday = useCollectionStore((s) => s.callsToday);
  const busyWith = useCollectionStore((s) => s.busyWith);
  const error = useCollectionStore((s) => s.error);
  const notice = useCollectionStore((s) => s.notice);
  const selectCurrency = useCollectionStore((s) => s.selectCurrency);
  const load = useCollectionStore((s) => s.load);
  const watch = useCollectionStore((s) => s.watch);
  const stopWatching = useCollectionStore((s) => s.stopWatching);
  const startCollection = useCollectionStore((s) => s.startCollection);

  const limited = useRateLimited();

  useEffect(() => {
    void load();
    watch();
    return () => stopWatching();
  }, [load, watch, stopWatching]);

  // 스트림이 `idle`을 보내면 `snapshot`이 비므로, 카드에 넘길 최소 형태를 만든다.
  const view = snapshot ?? {
    generatedAt: "",
    callsToday,
    currency,
    targetFrom: "",
    targetTo: "",
    coveredFrom: null,
    coveredThrough: null,
    busyWith,
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <CurrencyTabs value={currency} onChange={selectCurrency} />

      <div className="rounded-lg border border-gray-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <p className="text-sm text-gray-900">
            오늘 호출 <span className="font-semibold tabular-nums">{callsToday}</span>회
          </p>
        </div>
        <p className="mt-0.5 text-[11px] text-gray-500">
          참고 지표입니다 — 한도 판정은 출처 응답으로 합니다
        </p>
      </div>

      {error && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}
      {notice && <p className="text-xs text-gray-500">{notice}</p>}

      {limited && (
        <RateLimitBanner currency={currency} coveredThrough={view.coveredThrough} />
      )}

      <CurrencyCard snapshot={view} onStart={() => void startCollection()} />

      <IncompleteRecordNotice dropped={eventsDropped} />
      <EventList events={events} jobsKept={jobsKept} />
    </div>
  );
}
