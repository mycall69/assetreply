"use client";

/**
 * 부동산 투자 시뮬레이션 (T026·T039·T048·T050) — 009 FR-001~FR-007, FR-011, FR-014, FR-015, FR-028~FR-033, FR-036,
 * ui-wireframes E1~E7·E9.
 *
 * 주식·가상자산·예금 화면과 같은 구성이되 **종목 검색 대신 지역 풀다운 셋 → 단지 풀다운 → 평형 라디오 일곱**이고, 그 아래에 매입일·
 * 매입가(선택)를 넣어 실행한다. 원금은 원화만이라 통화 칸이 없다(FR-007). 결과는 보드 → 안내 줄 → 차트 → 월별 표·이력 순이고(넓은 창이면
 * 표 오른쪽에 이력 — 010 `TableWithHistory`), 그 아래 비교다. 받지 않은 구간이면 진행만 보이고 **부분 결과를 보여주지 않는다**(FR-011). 화면 아래에 출처를 밝힌다(FR-036, 헌법
 * 원칙 II).
 * 경로 이름(`realestate`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)와 사이드바가 함께 전제한다.
 */

import { useEffect, useMemo } from "react";
import { TableWithHistory } from "@/components/TableWithHistory";
import { AreaBucketPicker } from "@/components/realestate/AreaBucketPicker";
import { ComplexPicker } from "@/components/realestate/ComplexPicker";
import { RealEstateBoard } from "@/components/realestate/RealEstateBoard";
import { RealEstateHistory } from "@/components/realestate/RealEstateHistory";
import { RealEstateNotice } from "@/components/realestate/RealEstateNotice";
import { RealEstatePerformanceTable } from "@/components/realestate/RealEstatePerformanceTable";
import { RealEstateSimulationForm, startBoundFor } from "@/components/realestate/RealEstateSimulationForm";
import { RegionPicker } from "@/components/realestate/RegionPicker";
import { TradeCollectingNotice } from "@/components/realestate/TradeCollectingNotice";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { kstToday } from "@/lib/startDate";
import type { RealEstateRegionLevel } from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";

export default function RealEstatePage() {
  const {
    regions, selection, regionCollecting, regionProgress, regionFailure, complexes, tradeProgress,
    detailsProgress, areas, areasCollecting, error,
    input, summary, rows, condition, acquisition, resultTarget, series, seriesError, collecting, progress, startable,
    rejection, loading,
    loadSidos, selectSido, selectSgg, selectUmd, selectComplex, selectArea, setInput, run, refreshIfRan,
    resumeWatching, dispose,
    history, historySaveError, selectedHistory, comparison, comparing, comparisonError,
    restoreHistory, toggleHistory, removeHistoryEntry, rerunHistory, compareSelected,
  } = useRealEstateStore();

  // 화면을 열면 받는 중이던 작업을 다시 구독하고 시·도를 요청한다. 떠나면 진행 구독을 끊는다 — 수집은 서버에서 이어진다.
  useEffect(() => {
    resumeWatching();
    void loadSidos();
    return dispose;
  }, [resumeWatching, loadSidos, dispose]);
  // FR-034 — 설정 화면에 다녀왔을 수 있다. 실행한 결과가 있으면 새 보유세 기준 비율로 다시 받는다(008과 같다).
  useEffect(() => {
    void refreshIfRan();
  }, [refreshIfRan]);
  // FR-032 — 이력은 브라우저에 있다. 화면이 열릴 때 읽는다.
  useEffect(() => {
    restoreHistory();
  }, [restoreHistory]);

  // 매입일의 마지막 날 — 오늘(한국 시간). 화면을 연 때로 정한다(서버도 계산 끝을 한국 시간 오늘로 잡는다).
  const limit = useMemo(() => kstToday(), []);

  function selectRegion(level: RealEstateRegionLevel, code: string): void {
    if (level === "sido") void selectSido(code);
    else if (level === "sgg") void selectSgg(code);
    else void selectUmd(code);
  }

  // 실거래 진행 줄의 주어 — 고른 시·군·구의 이름.
  const sggName = regions.sgg?.find((r) => r.code === selection.sgg)?.name ?? null;
  // 그 시·군·구의 실거래를 다 받기 전에는 평형의 거래 수를 모른다(E2).
  const waitingForTrades = areas === null
    && (areasCollecting !== null || (complexes !== null && complexes.trades.state !== "collected"));
  const bucket = areas?.buckets.find((b) => b.key === selection.area) ?? null;

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">부동산 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">
          그때 이 아파트를 샀다면 — 취득 비용과 해마다 낸 보유세를 뺀 지금까지의 성과
        </p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <RegionPicker regions={regions} selection={selection} onSelect={selectRegion}
          collecting={regionCollecting} progress={regionProgress} failure={regionFailure} />
        <ComplexPicker complexes={complexes} value={selection.complexId}
          onChange={(complexId) => void selectComplex(complexId)} sggName={sggName}
          tradeProgress={tradeProgress} detailsProgress={detailsProgress} />
        <AreaBucketPicker areas={areas} value={selection.area} onChange={selectArea}
          waitingForTrades={waitingForTrades} />
        <RealEstateSimulationForm
          values={input}
          disabled={loading || bucket === null}
          limit={limit}
          areaLabel={bucket?.label ?? null}
          startBound={startBoundFor(bucket, startable)}
          rejection={rejection}
          onChange={setInput}
          onSubmit={() => void run()}
        />
      </section>

      {error !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      {collecting !== null && (
        // FR-011 — 진행을 보이되 부분 결과를 보여주지 않는다.
        <TradeCollectingNotice collecting={collecting} sggName={sggName} progress={progress} />
      )}

      {loading && <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>}

      {summary !== null && condition !== null && acquisition !== null && resultTarget !== null && (
        <div className="space-y-2">
          <RealEstateBoard result={{ ...resultTarget, condition, acquisition, summary }} />
          <RealEstateNotice summary={summary} />
        </div>
      )}

      {summary !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
          {seriesError !== null ? (
            // 표는 그대로 둔다 — 차트가 빈 것과 결과가 없는 것은 다른 사건이다.
            <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {seriesError}
            </p>
          ) : (
            // 점은 매달 — 첫 점은 매입일, 끝점은 보드. 추정 점은 표식, 시세 없음은 끊고, 잠정은 연한 색이다(E6).
            <PerformanceChart series={series} collecting={collecting} loading={loading} />
          )}
        </section>
      )}

      {/* 010 FR-015~FR-017 — 넓은 창이면 성과 표 오른쪽(sticky), 좁으면 지금처럼 표 아래. 경계는 표의 실제 폭이다. */}
      <TableWithHistory
        table={summary !== null ? (
          <section>
            <h3 className="mb-2 text-sm font-semibold">월별 투자 성과</h3>
            <RealEstatePerformanceTable rows={rows} taxGaps={summary.taxGaps} />
          </section>
        ) : null}
        history={(
          <RealEstateHistory
            entries={history}
            selected={selectedHistory}
            comparing={comparing}
            saveError={historySaveError}
            onToggle={toggleHistory}
            onRemove={removeHistoryEntry}
            onCompare={() => void compareSelected()}
            onRerun={(id) => void rerunHistory(id)}
          />
        )}
      />

      {(comparing || comparison.length > 0 || comparisonError !== null) && (
        // FR-033 — 모두 KRW 기준 수익률로 겹친다. 다른 자산군 이력과 섞이지 않는다.
        <ComparisonChart items={comparison} loading={comparing} error={comparisonError} />
      )}

      <p className="text-xs text-gray-400">
        출처: 국토교통부 아파트 매매 실거래가 공개 자료(공공데이터포털) · 행정안전부 법정동코드 · 공동주택관리정보시스템
      </p>
    </div>
  );
}
