"use client";

/**
 * 단지 고르기 (T026) — 009 FR-003, FR-011, FR-014, FR-015, ui-wireframes E1·E2·E9·접근성.
 *
 * - 항목은 "단지명 · YYYY년 입주 · N세대" — 모르는 값은 빼고 **지어내지 않는다**(FR-003)
 * - **같은 동에 이름이 같은 단지가 둘 이상이면 그 항목들 끝에 지번**을 붙인다. 이름이 겹치지 않으면 붙이지 않는다 — 같은 글자의 항목
 *   둘 중 무엇이 어느 단지인지 가를 수 없으면 엉뚱한 단지의 시세를 본다
 * - 기본 정보(세대수·입주년도)를 채우는 동안 받은 단지 / 단지 수, 그 시·군·구의 실거래를 받는 동안 006 `CollectingNotice`(주어
 *   "송파구"·"실거래", 단위 "개월")와 처음 시·군·구 안내(research R9-5)
 * - 단지 목록 자료를 받지 못했으면 빈 풀다운 대신 사유(FR-015), 실거래 수집이 실패했으면 E9의 문구·할 일(FR-014) — 둘 다
 *   `role="alert"`. 실패는 응답(`trades.failure`)에 남아 다시 열어도 보인다
 */

import { CollectingNotice } from "@/components/stock/CollectingNotice";
import type { RealEstateProgressSnapshot } from "@/lib/realEstateProgressStream";
import type { RealEstateComplex, RealEstateComplexesResponse, RealEstateTradeCollecting } from "@/lib/types";
import { realEstateFailureText } from "@/stores/realEstateStore";

const SELECT_ID = "realestate-complex";

/** 풀다운 항목의 글자. `withJibun`은 같은 동에 같은 이름의 단지가 또 있을 때다. */
export function complexLabel(complex: RealEstateComplex, withJibun: boolean): string {
  const parts = [complex.name];
  if (complex.moveInYear !== null) parts.push(`${complex.moveInYear}년 입주`);
  if (complex.households !== null) parts.push(`${complex.households.toLocaleString("ko-KR")}세대`);
  if (withJibun && complex.jibun !== null) parts.push(complex.jibun);
  return parts.join(" · ");
}

export function ComplexPicker({
  complexes,
  value,
  onChange,
  sggName,
  tradeProgress,
  detailsProgress,
}: {
  /** 동을 고르기 전에는 `null`이다. */
  complexes: RealEstateComplexesResponse | null;
  value: number | null;
  onChange: (complexId: number) => void;
  /** 실거래 진행 줄의 주어 — "송파구". */
  sggName: string | null;
  tradeProgress: RealEstateProgressSnapshot | null;
  detailsProgress: RealEstateProgressSnapshot | null;
}) {
  const items = complexes?.items ?? [];
  const sameName = new Map<string, number>();
  for (const c of items) sameName.set(c.name, (sameName.get(c.name) ?? 0) + 1);

  const placeholder = complexes === null ? "동을 먼저 고르세요"
    : items.length === 0 ? "고를 단지가 없습니다" : "단지를 고르세요";

  const trades = complexes?.trades ?? null;
  const failure = trades?.state === "failed" ? trades.failure : null;

  return (
    <div className="space-y-2 text-sm">
      <div className="flex items-center gap-3">
        <label htmlFor={SELECT_ID} className="w-10 text-gray-500">단지</label>
        <select
          id={SELECT_ID}
          value={value === null ? "" : String(value)}
          disabled={complexes === null || items.length === 0}
          onChange={(e) => {
            if (e.target.value !== "") onChange(Number(e.target.value));
          }}
          className="min-w-80 rounded border border-gray-300 px-2 py-1 disabled:bg-gray-50 disabled:text-gray-400"
        >
          <option value="" disabled>{placeholder}</option>
          {items.map((c) => (
            <option key={c.complexId} value={c.complexId}>
              {complexLabel(c, (sameName.get(c.name) ?? 0) > 1)}
            </option>
          ))}
        </select>
      </div>

      {complexes?.listError !== undefined && (
        <p role="alert" className="rounded border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
          ⚠ 단지 목록을 받지 못했습니다({complexes.listError.reason}). 실거래를 받은 단지만 보입니다.
        </p>
      )}

      {complexes?.details.pending === true && (
        <p className="text-xs text-gray-500">
          <span aria-hidden="true">⟳ </span>세대수·입주년도를 채우고 있습니다
          {detailsProgress !== null && detailsProgress.total > 0 && (
            <span className="tabular-nums">
              {" | "}{detailsProgress.done.toLocaleString("ko-KR")} / {detailsProgress.total.toLocaleString("ko-KR")}단지
            </span>
          )}
        </p>
      )}

      {complexes !== null && trades?.state === "collecting" && (
        <div className="space-y-1">
          <TradeNotice complexes={complexes} sggName={sggName} progress={tradeProgress} />
          <p className="text-xs text-gray-400">
            처음 고르는 시·군·구는 전체 이력을 받습니다(하루 한도로 30곳 남짓).
          </p>
        </div>
      )}

      {failure !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-3 py-2 text-red-700">
          ⚠ {realEstateFailureText(failure.kind, failure.reason)}
        </p>
      )}
    </div>
  );
}

/** 실거래 진행 줄 — 006 `CollectingNotice`. 스냅샷이 오기 전에는 응답의 받은 달 / 받을 달을 쓴다. */
function TradeNotice({
  complexes,
  sggName,
  progress,
}: {
  complexes: RealEstateComplexesResponse;
  sggName: string | null;
  progress: RealEstateProgressSnapshot | null;
}) {
  const { trades, umd } = complexes;
  const jobId = trades.jobId ?? 0;
  const collecting: RealEstateTradeCollecting = {
    status: "collecting", kind: "trade", lawdCd: umd.lawdCd, jobId,
    monthsDone: trades.monthsDone, monthsTotal: trades.monthsTotal, progressUrl: trades.progressUrl ?? "",
  };
  const current: RealEstateProgressSnapshot = progress ?? {
    jobId, kind: "trade", target: umd.lawdCd, status: "running",
    done: trades.monthsDone, total: trades.monthsTotal,
  };
  return (
    <CollectingNotice collecting={collecting} stockName={sggName ?? "이 시·군·구"} progress={current}
      subject="실거래" unit="개월" doneNote="끝나면 단지 목록에 없던 단지가 더해집니다." />
  );
}
