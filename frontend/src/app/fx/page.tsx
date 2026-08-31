"use client";

/**
 * 외환 분석 화면 (T033) — contracts/ui-wireframes.md W2.
 *
 * 001의 4개 탭(조회·스프레드·차트·수집현황)을 하나로 합친 화면이다. 통화·요약·차트·표가
 * 하나의 선택 날짜를 공유한다 (contracts/ui-interaction.md).
 */

import { useEffect } from "react";
import { CurrencyTabs } from "@/components/fx/CurrencyTabs";
import { DailyTable } from "@/components/fx/DailyTable";
import { DateHighlightInput } from "@/components/fx/DateHighlightInput";
import { RateSummary } from "@/components/fx/RateSummary";
import { TodayRefresh } from "@/components/fx/TodayRefresh";
import { TrendChart } from "@/components/fx/TrendChart";
import { PeriodPresets } from "@/components/fx/PeriodPresets";
import { EmptyState } from "@/components/EmptyState";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";

export default function FxPage() {
  const {
    currency, selectedDate, preset, latest, daily, series, collecting, notice,
    loading, error, setCurrency, setPreset, selectDate, loadAll, loadMoreDaily,
  } = useFxWorkspaceStore();

  useEffect(() => {
    void loadAll();
    // 진입 시 한 번만. 이후 갱신은 각 조작이 담당한다 (갱신 범위 표).
  }, [loadAll]);

  const noData = latest?.status === "no_data";

  return (
    <div className="mx-auto max-w-5xl space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">외환 데이터 분석</h2>
          <p className="mt-1 text-sm text-gray-500">매매기준율 및 히스토리컬 트렌드</p>
        </div>
        <CurrencyTabs value={currency} onChange={(c) => void setCurrency(c)} />
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
            <TrendChart
              series={series}
              collecting={collecting}
              selectedDate={selectedDate}
              loading={loading}
              onSelect={(d) => void selectDate(d)}
            />
          </section>

          <section>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-semibold">일자별 환율 상세</h3>
            </div>
            {daily && (
              <DailyTable
                data={daily}
                selectedDate={selectedDate}
                onSelect={(d) => void selectDate(d)}
                onLoadMore={() => void loadMoreDaily()}
              />
            )}
          </section>
        </>
      )}
    </div>
  );
}

function presetLabel(preset: string): string {
  const map: Record<string, string> = {
    "1m": "1개월", "6m": "6개월", "1y": "1년", "5y": "5년", "10y": "10년", all: "전체",
  };
  return map[preset] ?? preset;
}
