"use client";

/**
 * 대시보드 머리 — 오늘 날짜(한국 시간)·받은 시각·[새로고침] (014 T039) — FR-002, FR-008, contracts D1.
 *
 * 날짜는 **한국 시간**이다(브라우저 시간대와 무관). 화면을 열어 둔 채 한국 자정을 넘기면 바뀐다 — 연 순간의 날짜를 고정하면 밤새
 * 열어 둔 화면이 어제 날짜를 오늘로 보인다(FR-002 실패 양상). 서버가 그린 첫 화면에는 날짜를 두지 않는다 — 서버와 브라우저의
 * 시각이 달라 처음 그림이 어긋나지 않게 한다(`useSyncExternalStore`의 서버 값 "").
 *
 * [새로고침]은 지표 시세만 곧바로 다시 부른다(서버 캐시 30초 안이면 같은 값). 뉴스는 다시 부르지 않는다.
 */
import { useSyncExternalStore } from "react";
import { formatKstDate, formatZonedTime, KST_ZONE, msUntilNextKstMidnight } from "@/lib/kstClock";

function subscribe(onChange: () => void): () => void {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const arm = () => {
    timer = setTimeout(() => {
      onChange();
      arm();
    }, msUntilNextKstMidnight(new Date()) + 50);
  };
  arm();
  return () => {
    if (timer !== null) clearTimeout(timer);
  };
}

const today = () => formatKstDate(new Date());
const serverToday = () => "";

export function TodayHeader({ fetchedAt, onRefresh }: { fetchedAt: string | null; onRefresh: () => void }) {
  const date = useSyncExternalStore(subscribe, today, serverToday);
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">대시보드</h2>
        <p className="mt-1 text-sm text-gray-600">
          <span data-testid="today" className="font-medium text-gray-900">{date}</span>
          <span className="ml-2 text-gray-500">한국 시간</span>
        </p>
      </div>
      <div className="flex items-center gap-3 text-sm text-gray-500">
        {fetchedAt && <span>{formatZonedTime(fetchedAt, KST_ZONE)} 받음</span>}
        <button type="button" onClick={onRefresh}
          className="rounded border border-gray-300 px-3 py-1 text-gray-700 hover:bg-gray-50">새로고침</button>
      </div>
    </header>
  );
}
