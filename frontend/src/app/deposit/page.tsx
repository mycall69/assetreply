"use client";

/**
 * 예금 투자 시뮬레이션 (T021) — 008 FR-001~FR-007, FR-011, FR-016, FR-035, ui-wireframes D1~D4·D8.
 *
 * 주식·가상자산 화면과 같은 구성이되 **종목 검색 대신 투자처 라디오 버튼 다섯**이고, 원금은 원화만이다 — 통화 칸·재투자 칸이
 * 없다. 시작일 상한은 **오늘(한국 시간)**이다(FR-005). 화면 아래에 출처(ECOS)를 밝힌다(약관 제7조 ②, research R8-2).
 * 경로 이름(`deposit`)은 미구현 자산군 가드(`noUnbuiltAssetRoutes.test.ts`)와 사이드바가 함께 전제한다.
 *
 * 011 — 상품(정기예금 · 정기 적금)을 고른다(FR-022). 적금이면 여섯 칸 보드(`InstallmentBoard`)·적금 표(`InstallmentTable`)·누적 납입
 * 원금 점선과 적금 금리 선이 있는 차트를 그리고, 정기예금 보드·표는 없다(한 번에 한쪽만). 금액 칸은 "월 납입액"이다.
 */

import { useEffect, useMemo } from "react";
import { TableWithHistory } from "@/components/TableWithHistory";
import { DepositHistory } from "@/components/deposit/DepositHistory";
import { DepositNotice } from "@/components/deposit/DepositNotice";
import { DepositPerformanceTable } from "@/components/deposit/DepositPerformanceTable";
import { DepositSimulationForm } from "@/components/deposit/DepositSimulationForm";
import { InstallmentBoard } from "@/components/deposit/InstallmentBoard";
import { InstallmentTable } from "@/components/deposit/InstallmentTable";
import { InstitutionPicker } from "@/components/deposit/InstitutionPicker";
import { ProductPicker } from "@/components/deposit/ProductPicker";
import { CollectingNotice } from "@/components/stock/CollectingNotice";
import { ComparisonChart } from "@/components/stock/ComparisonChart";
import { PerformanceBoard } from "@/components/stock/PerformanceBoard";
import { PerformanceChart } from "@/components/stock/PerformanceChart";
import { depositBoardNotes } from "@/lib/boardNotes";
import { kstToday } from "@/lib/startDate";
import { INSTITUTION_NAMES, useDepositStore } from "@/stores/depositStore";

/** 적금 부제목(ui-wireframes §7). 정기예금 부제목은 지금 문장 그대로다(`DepositPage.test.tsx`). */
const INSTALLMENT_SUBTITLE = "매달 정해진 돈을 1년 만기 정기 적금에 붓고, 만기 금액은 1년 정기예금에 넣으며 새 적금을 붓는 성과";

/** 진행 안내의 받는 것 — 적금 실행은 계열(적금 금리 → 정기예금 금리)마다 받는다. */
const COLLECTING_SUBJECT = { installment: "적금 금리", deposit: "정기예금 금리" } as const;

export default function DepositPage() {
  const {
    input, product, installment, productNotice, setProduct,
    institutions, rows, summary, condition, resultName, series, seriesError, collecting,
    progress, startable,
    loading, error, setInput, selectInstitution, loadInstitutions, run, refreshIfRan, dispose,
    history, historySaveError, historyLoading, historyLoadError, historyNotice, retentionDays,
    selectedHistory, comparison, comparing, comparisonError,
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
  // FR-037 — 이력은 로컬 DB에 있다(012). 화면이 열릴 때 그 자산군의 옛 브라우저 이력을 옮긴 뒤 목록을 받는다(012 FR-013).
  useEffect(() => {
    void restoreHistory();
  }, [restoreHistory]);

  // 시작일의 마지막 날 — 오늘(한국 시간). 화면을 연 때로 정한다(서버도 계산 끝을 한국 시간 오늘로 잡는다).
  const limit = useMemo(() => kstToday(), []);

  // FR-035 — 기준 줄에 투자처·세율·지금 회차를 늘 보인다. 결과가 어느 조건의 것인지 확인할 수 있어야 한다.
  // 013 반복 2026-10-09b — 글자는 비교 화면의 투자 시뮬레이션 모달과 같은 함수가 만든다(`lib/boardNotes`).
  const notes = summary === null ? []
    : depositBoardNotes(summary, condition, resultName ?? INSTITUTION_NAMES[input.institution]);

  return (
    <div className="space-y-5">
      <header>
        <h2 className="text-2xl font-bold tracking-tight">예금 투자 시뮬레이션</h2>
        <p className="mt-1 text-sm text-gray-500">
          {product === "installment" ? INSTALLMENT_SUBTITLE
            : "1년 만기 정기예금에 가입하고 만기마다 세후 이자를 더해 재예치한 성과"}
        </p>
      </header>

      <section className="space-y-3 rounded-lg border border-gray-200 p-4">
        {/* 011 FR-022 — 상품. 바꾸면 결과가 빈다(조건은 남는다). */}
        <ProductPicker value={product} disabled={loading} onChange={setProduct} />
        <InstitutionPicker institutions={institutions} value={input.institution} product={product}
          onChange={selectInstitution} />
        {productNotice !== null && (
          <p role="status" className="text-xs text-amber-800">ⓘ {productNotice}</p>
        )}
        <DepositSimulationForm
          principalLabel={product === "installment" ? "월 납입액" : "투자 원금"}
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
          progress={progress} subject={collecting.series === undefined ? "금리" : COLLECTING_SUBJECT[collecting.series]}
          unit="개월" />
      )}

      {loading && <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>}

      {installment !== null && (
        <div className="space-y-2">
          {/* 011 FR-031 — 적금 보드(여섯 칸). 잠정·멈춤·확인 실패 줄은 정기예금과 같은 부품이다. */}
          <InstallmentBoard summary={installment.summary} institutionName={installment.name}
            taxRate={installment.condition.interestTaxRate} />
          <DepositNotice summary={installment.summary} start={installment.condition.start} />
        </div>
      )}

      {installment !== null && (
        <section>
          <h3 className="mb-2 text-sm font-semibold">성과 추이</h3>
          {installment.seriesError !== null ? (
            <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
              {installment.seriesError}
            </p>
          ) : (
            // 평가액·수익률·누적 납입 원금 선과 그 달 적금 금리 선. 상자에 그 달 정기예금 금리도 보인다(FR-032).
            <PerformanceChart series={installment.series} collecting={collecting} loading={loading} />
          )}
        </section>
      )}

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

      {/* 010 FR-015~FR-017 — 넓은 창이면 성과 표 오른쪽(sticky), 좁으면 지금처럼 표 아래. 경계는 표의 실제 폭이다. */}
      <TableWithHistory
        table={installment !== null ? (
          <section>
            <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
            <InstallmentTable rows={installment.rows} />
          </section>
        ) : summary !== null ? (
          <section>
            <h3 className="mb-2 text-sm font-semibold">일자별 투자 성과</h3>
            <DepositPerformanceTable rows={rows} />
          </section>
        ) : null}
        history={(
          <DepositHistory
            entries={history}
            selected={selectedHistory}
            comparing={comparing}
            saveError={historySaveError}
            loading={historyLoading}
            loadError={historyLoadError}
            onRetry={() => void restoreHistory()}
            notice={historyNotice}
            retentionDays={retentionDays}
            onToggle={toggleHistory}
            onRemove={(id) => void removeHistoryEntry(id)}
            onCompare={() => void compareSelected()}
            onRerun={(id) => void rerunHistory(id)}
          />
        )}
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
