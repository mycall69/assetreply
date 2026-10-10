"use client";

/**
 * 지표 모달의 내용 (014 T061 → 반복 2026-10-10b T121) — FR-010~FR-016, FR-018, FR-019, FR-027~FR-029, contracts D3·D4·D7·D8.
 *
 * 머리 → 변화 까닭 → 기간 단추 → 그래프 → 일자별 표. 모달의 껍데기(대화 상자·닫기·포커스)는 `IndicatorModal`이 진다.
 *
 * - 머리 값은 대시보드와 같은 스토어다(FR-010)
 * - 기간 단추는 스토어를 먼저 바꾸고 주소의 `range`를 바꾼다(`router.replace`, 스크롤 유지) — 새로고침·즐겨찾기에서 같은 기간이다.
 *   주소가 바뀌어 다시 그려질 때 같은 기간을 두 번 받지 않는다
 * - 받는 중·실패는 일봉 기간의 그래프 자리와 표 자리에 같은 글이다(D4). 장중(일·주)은 수집과 무관하게 그린다
 * - 그래프가 다 받아지면(`ready`) 받는 중이던 표도 다시 연다 — 표만 받는 중으로 남지 않게
 */
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { IndicatorChart } from "@/components/dashboard/IndicatorChart";
import { IndicatorCommentary } from "@/components/dashboard/IndicatorCommentary";
import { IndicatorHeader } from "@/components/dashboard/IndicatorHeader";
import { IndicatorTable } from "@/components/dashboard/IndicatorTable";
import { RangePicker } from "@/components/dashboard/RangePicker";
import { SeriesCollecting } from "@/components/dashboard/SeriesCollecting";
import type { IndicatorRange } from "@/lib/types";
import { useIndicatorCommentaryStore, type CommentaryEntry } from "@/stores/indicatorCommentaryStore";
import { useIndicatorSeriesStore } from "@/stores/indicatorSeriesStore";
import { useIndicatorTableStore } from "@/stores/indicatorTableStore";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";

const LOADING: CommentaryEntry = { status: "loading", body: null };

export function IndicatorView({ id, range, titleId, onClose }: {
  id: string;
  range: IndicatorRange;
  /** 대화 상자의 이름이 되는 제목의 `id`. */
  titleId?: string;
  /** 없는 지표 안내의 [닫기]. */
  onClose: () => void;
}) {
  const router = useRouter();
  const quotes = useMarketQuotesStore((s) => s.data);
  const status = useIndicatorSeriesStore((s) => s.status);
  const series = useIndicatorSeriesStore((s) => s.series);
  const collecting = useIndicatorSeriesStore((s) => s.collecting);
  const current = useIndicatorSeriesStore((s) => s.range);
  const open = useIndicatorSeriesStore((s) => s.open);
  const setRange = useIndicatorSeriesStore((s) => s.setRange);
  const reload = useIndicatorSeriesStore((s) => s.reload);
  const retryCollect = useIndicatorSeriesStore((s) => s.retryCollect);
  const closeSeries = useIndicatorSeriesStore((s) => s.close);
  const table = useIndicatorTableStore();
  const commentary = useIndicatorCommentaryStore((s) => s.entries[id]) ?? LOADING;
  const loadCommentary = useIndicatorCommentaryStore((s) => s.load);

  useEffect(() => {
    const s = useIndicatorSeriesStore.getState();
    if (s.id === id && s.range === range && s.status !== "idle") return;
    void open(id, range);
  }, [id, range, open]);
  useEffect(() => () => closeSeries(), [closeSeries]);

  const openTable = table.open;
  const closeTable = table.close;
  useEffect(() => {
    void openTable(id);
    return () => closeTable();
  }, [id, openTable, closeTable]);

  useEffect(() => {
    void loadCommentary(id);
  }, [id, loadCommentary]);

  // 그래프가 일봉 기간으로 다 받아졌는데 표가 받는 중·실패로 남았으면 다시 연다
  const dailyReady = status === "ready" && series !== null && !("intraday" in series);
  const tableWaiting = table.status === "collecting" || table.status === "failed";
  useEffect(() => {
    if (dailyReady && tableWaiting) void openTable(id);
  }, [dailyReady, tableWaiting, id, openTable]);

  const card = quotes?.indicators.find((i) => i.id === id) ?? null;
  const name = series?.indicator.name ?? collecting?.indicator.name ?? card?.name ?? id;
  const shown = status === "idle" ? range : current;
  const retry = () => void retryCollect();

  // 없는 지표는 이 부품 안에서 안내한다 — 부품을 내리면 닫힐 때 스토어가 비워져 다시 열리며 같은 요청을 되풀이한다
  if (status === "not_found") {
    return (
      <div className="space-y-3 py-6 text-center">
        <p id={titleId} className="text-gray-700">없는 지표입니다: &quot;{id}&quot;</p>
        <button type="button" onClick={onClose} className="text-sm underline">닫기</button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <IndicatorHeader card={card} series={series} name={name} onRetry={retry} titleId={titleId} />
      <IndicatorCommentary state={commentary} onRetry={() => void loadCommentary(id)} />
      <RangePicker value={shown} onChange={(next) => {
        void setRange(next, (r) => router.replace(`?range=${r}`, { scroll: false }));
      }} />
      {status === "ready" && series && <IndicatorChart series={series} onRetry={() => void reload()} />}
      {(status === "collecting" || status === "failed") && collecting && (
        <SeriesCollecting collecting={collecting} name={name} onRetry={retry} />
      )}
      {status === "loading" && <p className="text-sm text-gray-500">이력을 불러오는 중…</p>}
      {status === "error" && <p role="alert" className="text-sm text-amber-800">이력을 불러오지 못했습니다.</p>}
      {(table.status === "ready" || table.status === "loading") && table.table && (
        <IndicatorTable
          table={{ ...table.table, rows: table.rows, hasMore: table.hasMore, oldestReturned: table.oldestReturned }}
          period={table.period}
          onPeriod={(p) => void table.setPeriod(p)}
          onMore={() => void table.loadMore()}
          loading={table.loadingMore}
          error={table.loadError}
          switching={table.status === "loading"}
        />
      )}
      {(table.status === "collecting" || table.status === "failed") && table.collecting && (
        <SeriesCollecting collecting={table.collecting} name={name} onRetry={retry} />
      )}
      {table.status === "loading" && !table.table && <p className="text-sm text-gray-500">일자별 표를 불러오는 중…</p>}
      {table.status === "error" && <p role="alert" className="text-sm text-amber-800">일자별 표를 불러오지 못했습니다.</p>}
    </div>
  );
}
