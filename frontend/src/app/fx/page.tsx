"use client";

/**
 * 외환 분석 화면 (T033) — contracts/ui-wireframes.md W2.
 *
 * 001의 4개 탭(조회·스프레드·차트·수집현황)을 하나로 합친 화면이다. 통화·요약·차트·표가
 * 하나의 선택 날짜를 공유한다 (contracts/ui-interaction.md).
 *
 * 010 반복 1 — 다른 네 화면처럼 왼쪽에서 시작한다(FR-022). 통화를 바꾸면 요약·차트·표가 "불러오는 중"으로 바뀌어 문서가 창보다 짧아지고, 브라우저가
 * 스크롤을 끌어내렸다(R10-16 실측). 그래서 바꾸기 **직전** 본문 높이를 최소 높이로 붙잡고, 새 통화가 다 오면 놓는다(FR-023).
 * 기간 단위 전환도 높이를 붙잡되, 새 표가 붙으면 표의 처음으로 옮긴다(004 FR-005b 그대로 — T051 실측).
 */

import { useEffect, useRef, useState } from "react";
import { CurrencyTabs } from "@/components/fx/CurrencyTabs";
import { PeriodTabs } from "@/components/fx/PeriodTabs";
import { DailyTable } from "@/components/fx/DailyTable";
import { DateHighlightInput } from "@/components/fx/DateHighlightInput";
import { RateSummary } from "@/components/fx/RateSummary";
import { TodayRefresh } from "@/components/fx/TodayRefresh";
import { TrendChart } from "@/components/fx/TrendChart";
import { PeriodPresets } from "@/components/fx/PeriodPresets";
import { EmptyState } from "@/components/EmptyState";
import type { CurrencyCode } from "@/lib/types";
import { PRESETS, useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";

export default function FxPage() {
  const {
    currency, selectedDate, preset, period, latest, daily, series, collecting,
    notice, presetNotice, loading, error, loadingMore, loadMoreError, tableEpoch,
    setCurrency, setPreset, setPeriod, selectDate, loadAll, loadMoreDaily,
  } = useFxWorkspaceStore();

  useEffect(() => {
    void loadAll();
    // 진입 시 한 번만. 이후 갱신은 각 조작이 담당한다 (갱신 범위 표).
  }, [loadAll]);

  const noData = latest?.status === "no_data";

  // FR-023 — 다시 받는 동안 붙잡는 본문 높이(px). 빠르게 두 번 바꾸면 늦게 끝난 앞 전환이 뒤 전환의 높이를 놓지 않게 차례를 센다.
  const workspace = useRef<HTMLDivElement>(null);
  const [reserve, setReserve] = useState<number | null>(null);
  const turn = useRef(0);
  function holdWhile(reload: () => Promise<void>): void {
    const height = workspace.current?.getBoundingClientRect().height ?? 0;
    const mine = ++turn.current;
    setReserve(height > 0 ? height : null);
    void reload().finally(() => {
      if (turn.current === mine) setReserve(null);
    });
  }

  // 004 FR-005b — 기간 단위를 바꾸면 표가 떨어졌다 새로 붙는다. 새로 붙은 `DailyTable`은 직전 `resetKey`를 모르므로 화면이 마지막으로 그린
  // 표의 차례를 기억해 표의 처음으로 옮긴다. 통화 전환은 차례를 올리지 않아 창이 그대로다(FR-023). 표가 붙은 채 바뀌는 경우(먼 날짜)는
  // `DailyTable`도 같은 자리로 옮긴다 — 표를 바로 감싼 자리라 두 번 옮겨도 같다.
  const tableTop = useRef<HTMLDivElement>(null);
  const shownEpoch = useRef(tableEpoch);
  useEffect(() => {
    if (daily === null || shownEpoch.current === tableEpoch) return;
    shownEpoch.current = tableEpoch;
    tableTop.current?.scrollIntoView?.({ block: "start" });
  }, [daily, tableEpoch]);

  return (
    <div ref={workspace} className="max-w-5xl space-y-5"
      style={reserve === null ? undefined : { minHeight: `${reserve}px` }}>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">외환 데이터 분석</h2>
          <p className="mt-1 text-sm text-gray-500">매매기준율 및 히스토리컬 트렌드</p>
        </div>
        <CurrencyTabs value={currency} onChange={(c: CurrencyCode) => holdWhile(() => setCurrency(c))} />
      </header>

      {error && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {noData ? (
        <EmptyState />
      ) : (
        <>
          <section className="grid gap-4 md:grid-cols-2">
            <div className="relative">
              {latest && <RateSummary latest={latest} />}
              <div className="absolute right-4 top-4">
                <TodayRefresh currency={currency} onRefreshed={() => void loadAll()} />
              </div>
            </div>
            <DateHighlightInput
              value={selectedDate}
              notice={notice}
              onChange={(d) => void selectDate(d)}
            />
          </section>

          <section className="rounded-lg border border-gray-200 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">
                환율 트렌드 ({presetLabel(preset)})
              </h3>
              <PeriodPresets value={preset} onChange={(p) => void setPreset(p)} />
            </div>

            {presetNotice && (
              // FR-019 — 요청 구간이 축적 범위를 넘어 잘렸음을 알린다. 알리지 않으면
              // 축적이 짧은 통화에서 여러 프리셋이 같은 차트를 그리는데 이유를 알 수
              // 없어, 사용자는 버튼이 먹지 않는다고 여긴다 (SC-012).
              <p
                role="status"
                data-testid="preset-clamp-notice"
                className="mb-2 rounded border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800"
              >
                {presetNotice.message}
              </p>
            )}

            <TrendChart
              series={series}
              collecting={collecting}
              selectedDate={selectedDate}
              loading={loading}
              onSelect={(d) => void selectDate(d)}
            />
          </section>

          <section>
            {/*
              왼쪽이 "무엇을 볼지", 오른쪽이 "가져갈지"다. 내려받기는 표 안에 둔다
              (contracts/ui-wireframes.md W1).
            */}
            <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
              <h3 className="text-sm font-semibold">일자별 환율 상세</h3>
              <PeriodTabs value={period} onChange={(p) => holdWhile(() => setPeriod(p))} />
            </div>
            {daily ? (
              <div ref={tableTop}>
                <DailyTable
                  data={daily}
                  selectedDate={selectedDate}
                  onSelect={(d) => void selectDate(d)}
                  onLoadMore={() => void loadMoreDaily()}
                  loadingMore={loadingMore}
                  loadError={loadMoreError}
                  resetKey={tableEpoch}
                />
              </div>
            ) : (
              <p role="status" className="rounded-lg border border-gray-200 px-4 py-6 text-center text-sm text-gray-500">
                ⟳ 불러오는 중…
              </p>
            )}
          </section>
        </>
      )}
    </div>
  );
}

/**
 * 차트 제목에 쓸 한글 이름. `PRESETS`에서 끌어온다 — 목록을 따로 적어 두면 프리셋을
 * 더할 때 한쪽만 고쳐 제목이 `20y`처럼 키를 그대로 노출한다.
 */
function presetLabel(preset: string): string {
  return PRESETS.find((p) => p.key === preset)?.label ?? preset;
}
