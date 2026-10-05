"use client";

/**
 * 부동산 투자 시뮬레이션 (T026) — 009 FR-001~FR-004, FR-007, FR-011, FR-014, FR-015, FR-036, ui-wireframes E1·E2·E9.
 *
 * 주식·가상자산·예금 화면과 같은 구성이되 **종목 검색 대신 지역 풀다운 셋 → 단지 풀다운 → 평형 라디오 일곱**이다. 원금은 원화만이라
 * 통화 칸이 없다(FR-007). 화면 아래에 출처를 밝힌다(FR-036, 헌법 원칙 II). 매입일·매입가·결과는 Phase 4(T039)가 더한다.
 * 경로 이름(`realestate`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)와 사이드바가 함께 전제한다.
 */

import { useEffect } from "react";
import { AreaBucketPicker } from "@/components/realestate/AreaBucketPicker";
import { ComplexPicker } from "@/components/realestate/ComplexPicker";
import { RegionPicker } from "@/components/realestate/RegionPicker";
import type { RealEstateRegionLevel } from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";

export default function RealEstatePage() {
  const {
    regions, selection, regionCollecting, regionProgress, regionFailure, complexes, tradeProgress,
    detailsProgress, areas, areasCollecting, error,
    loadSidos, selectSido, selectSgg, selectUmd, selectComplex, selectArea, resumeWatching, dispose,
  } = useRealEstateStore();

  // 화면을 열면 받는 중이던 작업을 다시 구독하고 시·도를 요청한다. 떠나면 진행 구독을 끊는다 — 수집은 서버에서 이어진다.
  useEffect(() => {
    resumeWatching();
    void loadSidos();
    return dispose;
  }, [resumeWatching, loadSidos, dispose]);

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
      </section>

      {error !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {error}
        </p>
      )}

      <p className="text-xs text-gray-400">
        출처: 국토교통부 아파트 매매 실거래가 공개 자료(공공데이터포털) · 행정안전부 법정동코드 · 공동주택관리정보시스템
      </p>
    </div>
  );
}
