"use client";

/**
 * 대시보드 (014 T040·T079) — FR-001~FR-009, FR-020~FR-025, contracts D1.
 *
 * 오늘 날짜(한국 시간)와 지표 15개 카드, 그 아래 뉴스 세 칸. 카드는 보이는 동안 서버가 정한 주기(기본 60초)로 다시 받는다
 * (FR-008). 한 지표가 실패해도 나머지 카드는 그대로다(FR-009). 뉴스는 카드와 따로 받는다 — 가장 느린 뉴스 출처가 카드를
 * 늦추지 않는다(FR-024). [새로고침]은 시세만 다시 부른다. 시뮬레이션이 아니라 조회 화면이다 — 이력을 쓰지 않는다.
 */
import { useEffect } from "react";
import { IndicatorGroups } from "@/components/dashboard/IndicatorGroups";
import { NewsSection } from "@/components/dashboard/NewsSection";
import { TodayHeader } from "@/components/dashboard/TodayHeader";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";

export default function DashboardPage() {
  const data = useMarketQuotesStore((s) => s.data);
  const status = useMarketQuotesStore((s) => s.status);
  const error = useMarketQuotesStore((s) => s.error);
  const load = useMarketQuotesStore((s) => s.load);
  const retry = useMarketQuotesStore((s) => s.retry);
  const startPolling = useMarketQuotesStore((s) => s.startPolling);
  const stopPolling = useMarketQuotesStore((s) => s.stopPolling);

  useEffect(() => {
    void load();
    startPolling();
    return () => stopPolling();
  }, [load, startPolling, stopPolling]);

  return (
    <div className="space-y-6">
      <TodayHeader fetchedAt={data?.fetchedAt ?? null} onRefresh={() => void load()} />
      {status === "error" && error && (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">{error}</p>
      )}
      {!data && status !== "error" && <p className="text-sm text-gray-500">지표 시세를 받는 중…</p>}
      {data && <IndicatorGroups indicators={data.indicators} onRetry={() => void retry()} />}
      <p className="text-xs text-gray-500">출처: Yahoo Finance(지수·원자재·VIX·시장 환율) · 한국은행 ECOS(환율 추이)</p>
      <NewsSection />
    </div>
  );
}
