"use client";

/**
 * 지표 화면 (014 T061) — FR-010~FR-016, FR-018, FR-019, contracts D3·D4.
 *
 * - 머리 값은 대시보드와 같은 스토어다. 열려 있는 동안 다시 받는다(U1 — 마운트에 시작, 언마운트에 멈춤)
 * - 단위 단추는 주소의 `unit`을 바꾼다(`router.replace`, 스크롤 유지) — 새로고침·즐겨찾기에서 같은 단위다
 * - 받는 중·실패·없는 지표는 각자의 안내다
 */
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import { IndicatorHeader } from "@/components/dashboard/IndicatorHeader";
import { SeriesCollecting } from "@/components/dashboard/SeriesCollecting";
import { UnitPicker } from "@/components/dashboard/UnitPicker";
import type { IndicatorUnit } from "@/lib/types";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";

export function IndicatorView({ id, unit }: { id: string; unit: IndicatorUnit }) {
  const router = useRouter();
  const quotes = useMarketQuotesStore((s) => s.data);
  const loadQuotes = useMarketQuotesStore((s) => s.load);
  const startPolling = useMarketQuotesStore((s) => s.startPolling);
  const stopPolling = useMarketQuotesStore((s) => s.stopPolling);
  const status = useIndicatorSeriesStore((s) => s.status);
  const series = useIndicatorSeriesStore((s) => s.series);
  const collecting = useIndicatorSeriesStore((s) => s.collecting);
  const current = useIndicatorSeriesStore((s) => s.unit);
  const open = useIndicatorSeriesStore((s) => s.open);
  const setUnit = useIndicatorSeriesStore((s) => s.setUnit);
  const retryCollect = useIndicatorSeriesStore((s) => s.retryCollect);
  const close = useIndicatorSeriesStore((s) => s.close);

  useEffect(() => {
    void loadQuotes();
    startPolling();
    return () => stopPolling();
  }, [loadQuotes, startPolling, stopPolling]);

  // 단위 단추는 스토어를 먼저 바꾸고 주소를 바꾼다 — 주소가 바뀌어 다시 그려질 때 같은 단위를 두 번 받지 않는다.
  useEffect(() => {
    const s = useIndicatorSeriesStore.getState();
    if (s.id === id && s.unit === unit && s.status !== "idle") return;
    void open(id, unit);
  }, [id, unit, open]);
  useEffect(() => () => close(), [close]);

  const card = quotes?.indicators.find((i) => i.id === id) ?? null;
  const name = series?.indicator.name ?? collecting?.indicator.name ?? card?.name ?? id;
  const shown = status === "idle" ? unit : current;

  if (status === "not_found") {
    return (
      <section className="space-y-3 py-10 text-center">
        <p className="text-gray-700">없는 지표입니다: &quot;{id}&quot;</p>
        <Link href="/dashboard" className="text-sm underline">대시보드로</Link>
      </section>
    );
  }

  return (
    <div className="space-y-4">
      <Link href="/dashboard" className="text-sm text-gray-600 underline">← 대시보드로</Link>
      <IndicatorHeader card={card} series={series} name={name} onRetry={() => void retryCollect()} />
      <UnitPicker value={shown} onChange={(next) => {
        void setUnit(next, (u) => router.replace(`?unit=${u}`, { scroll: false }));
      }} />
      {status === "ready" && series && <IndicatorChart series={series} />}
      {(status === "collecting" || status === "failed") && collecting && (
        <SeriesCollecting collecting={collecting} name={name} onRetry={() => void retryCollect()} />
      )}
      {status === "loading" && <p className="text-sm text-gray-500">이력을 불러오는 중…</p>}
      {status === "error" && <p role="alert" className="text-sm text-amber-800">이력을 불러오지 못했습니다.</p>}
    </div>
  );
}
