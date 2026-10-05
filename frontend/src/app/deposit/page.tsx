"use client";

/**
 * 예금 투자 시뮬레이션 (T021) — 008 FR-001~FR-007, FR-011, FR-016, FR-035, ui-wireframes D1~D4·D8.
 *
 * 주식·가상자산 화면과 같은 구성이되 **종목 검색 대신 투자처 라디오 버튼 다섯**이고, 원금은 원화만이다 — 통화 칸·재투자 칸이
 * 없다. 시작일 상한은 **오늘(한국 시간)**이다(FR-005). 화면 아래에 출처(ECOS)를 밝힌다(약관 제7조 ②, research R8-2).
 * 경로 이름(`deposit`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)와 사이드바가 함께 전제한다.
 */

import { useEffect, useMemo } from "react";
import { DepositHistory } from "@/components/deposit/DepositHistory";
import { DepositNotice } from "@/components/deposit/DepositNotice";
import { DepositPerformanceTable } from "@/components/deposit/DepositPerformanceTable";
import { DepositSimulationForm } from "@/components/deposit/DepositSimulationForm";
import { InstitutionPicker } from "@/components/deposit/InstitutionPicker";
import { CollectingNotice } from "@/components/stock/CollectingNotice";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { formatAnnualRate, shiftDecimal } from "@/lib/format";
import { kstToday } from "@/lib/startDate";
import { INSTITUTION_NAMES, useDepositStore } from "@/stores/depositStore";

/** 세율 `"0.154000"` → `15.4%` — 끝의 0을 지운다. 문자열로만 옮긴다(헌법 원칙 VI). */
export function taxPercent(rate: string): string {
  const shifted = shiftDecimal(rate, 2);
  const trimmed = shifted.includes(".") ? shifted.replace(/0+$/, "").replace(/\.$/, "") : shifted;
  return `${trimmed}%`;
}

export default function DepositPage() {
  const {
    input, institutions, rows, summary, condition, resultName, series, seriesError, collecting,
    progress, startable,
    loading, error, setInput, selectInstitution, loadInstitutions, run, refreshIfRan, dispose,
    history, historySaveError, selectedHistory, comparison, comparing, comparisonError,
    restoreHistory, toggleHistory, removeHistoryEntry, rerunHistory, compareSelected,
  } = useDepositStore();

  // FR-031 — 설정 화면에 다녀왔을 수 있다. 실행한 결과가 있으면 새 세율로 다시 받는다.
  useEffect(() => {
    void refreshIfRan();
  }, [refreshIfRan]);
  // 화면을 떠나면 진행 구독을 끊는다.
  useEffect(() => dispose, [dispose]);
  // 투자처의 설명과 받아 둔 범위(시작 가능 달).
  useEffect(() => {
    void loadInstitutions();
  }, [loadInstitutions]);
  // FR-037 — 이력은 브라우저에 있다. 화면이 열릴 때 읽는다.
  useEffect(() => {
    restoreHistory();
  }, [restoreHistory]);

  // 시작일의 마지막 날 — 오늘(한국 시간). 화면을 연 때로 정한다(서버도 계산 끝을 한국 시간 오늘로 잡는다).
  const limit = useMemo(() => kstToday(), []);

  // FR-035 — 기준 줄에 투자처·세율·지금 회차를 늘 보인다. 결과가 어느 조건의 것인지 확인할 수 있어야 한다.
  const notes: string[] = [];
  if (summary !== null) {
    notes.push(resultName ?? INSTITUTION_NAMES[input.institution]);
    if (condition !== null) notes.push(`세율 ${taxPercent(condition.interestTaxRate)}`);
    const term = summary.currentTerm;
    if (term !== null) {
      notes.push(`지금 회차 ${term.joinedOn} 가입 · ${formatAnnualRate(term.rate)} · 만기 ${term.maturesOn}`);
    }
  }

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">예금 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">
          1년 만기 정기예금에 가입하고 만기마다 세후 이자를 더해 재예치한 성과
        </p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        <InstitutionPicker institutions={institutions} value={input.institution}
          onChange={selectInstitution} />
        <DepositSimulationForm
          values={{ start: input.start, principal: input.principal }}
          disabled={loading}
          limit={limit}
          startable={startable}
          onChange={(next) => setInput(next)}
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
        <CollectingNotice collecting={collecting} stockName={INSTITUTION_NAMES[collecting.institution]}
          progress={progress} subject="금리" unit="개월" />
      )}

      {loading && <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>}

      {summary !== null && (
        <div className="space-y-2">
          {/* 멈춤은 사유(빈 금리 달)와 함께 아래 줄이 말한다 — 시세 기준의 문구를 쓰지 않는다. */}
          <PerformanceBoard summary={summary} currency="KRW" notes={notes} notFinalNotice={false} />
          <DepositNotice summary={summary} start={condition?.start ?? input.start} />
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
            // 점은 표의 행 날짜 + 계산 끝. 잠정 구간은 연한 색이다(FR-036, D5).
            <PerformanceChart series={series} collecting={collecting} loading={loading} />
          )}
        </section>
      )}

      {summary !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
          <DepositPerformanceTable rows={rows} />
        </section>
      )}

      <DepositHistory
        entries={history}
        selected={selectedHistory}
        comparing={comparing}
        saveError={historySaveError}
        onToggle={toggleHistory}
        onRemove={removeHistoryEntry}
        onCompare={() => void compareSelected()}
        onRerun={(id) => void rerunHistory(id)}
      />

      {(comparing || comparison.length > 0 || comparisonError !== null) && (
        // FR-038 — 모두 KRW 기준 수익률로 겹친다. 주식·가상자산 이력과 섞이지 않는다.
        <ComparisonChart items={comparison} loading={comparing} error={comparisonError} />
      )}

      <p className="text-xs text-gray-400">
        출처: 한국은행 경제통계시스템(ECOS) · 신규취급액 기준 가중평균 금리
      </p>
    </div>
  );
}
