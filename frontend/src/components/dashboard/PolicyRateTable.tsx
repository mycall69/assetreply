"use client";

/**
 * 기준금리 칸 (014 반복 2026-10-11d T209) — FR-040, SC-025, contracts D18.
 *
 * 대시보드의 "환율" 묶음 바로 뒤·"원자재·변동성" 묶음 앞의 **표**다 — 지표 카드가 아니다(묶음 이름표 `data-group`이 없다). 다섯 행: 국기·이름·
 * 금리·전회대비·기준 일자. 금리·전회대비는 서버 글자에 형식만 입힌다(원칙 VI) — 오르면 ▲ 빨강, 내리면 ▼ 파랑, 같으면 `0.00` 회색(지표 카드와
 * 같은 색 — 색만으로 구별하지 않는다). 기준 일자는 최근 결정의 한국 날짜다(`09. 17.` — 올해가 아니면 연도를 붙인다).
 *
 * 은행마다 따로 실패한다 — 받아 둔 값이 있으면 그 값과 "최근 갱신 실패", 없으면 까닭과 [다시 시도](수집 깨우기). 행의 이름은 그 은행의 금리 모달
 * 링크다(`/dashboard/{은행}?range=1y`) — 닫으면 이 링크로 포커스가 돌아온다(`data-rate`).
 */
import Link from "next/link";
import { failureLabel } from "@/components/dashboard/IndicatorHeader";
import { KST_ZONE, formatZonedTime } from "@/lib/kstClock";
import { dottedDate, kstYear, shortDottedDate } from "@/lib/rateFormat";
import type { PolicyRateRow } from "@/lib/types";
import { usePolicyRateStore } from "@/stores/policyRateStore";

const CELL = "whitespace-nowrap px-3 py-2 text-right tabular-nums";

export function rateTone(direction: PolicyRateRow["direction"]): string {
  if (direction === "up") return "text-red-700";
  if (direction === "down") return "text-blue-700";
  return "text-gray-500";
}

/** "▲ 0.25" · "▼ 0.25" · "0.00" · 첫 결정 "—". */
export function rateChangeText(change: string | null, direction: PolicyRateRow["direction"]): string {
  if (change === null) return "—";
  const magnitude = change.replace(/^-/, "");
  if (direction === "up") return `▲ ${magnitude}`;
  if (direction === "down") return `▼ ${magnitude}`;
  return magnitude;
}

function valueText(row: PolicyRateRow): string {
  if (row.rate !== null) return `${row.rate}%`;
  if (row.state === "failed") return failureLabel(row.failure?.kind);
  return "받는 중…";
}

function RateRow({ row, year, onRetry }: { row: PolicyRateRow; year: string; onRetry: () => void }) {
  const stale = row.rate !== null && row.failure !== null;
  return (
    <tr data-testid="rate-row" data-rate={row.bank} className="border-b border-gray-100">
      <td className="px-3 py-2 text-left">
        <Link href={`/dashboard/${row.bank}?range=1y`} aria-label={`${row.name} 금리 추이 보기`}
          className="inline-flex items-center gap-2 rounded text-gray-900 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-900">
          <span aria-hidden="true">{row.flag}</span>
          <span>{row.name}</span>
        </Link>
        {stale && row.failure && (
          <p data-testid={`rate-stale-${row.bank}`} className="text-xs text-amber-800">
            최근 갱신 실패 — {failureLabel(row.failure.kind)} · {formatZonedTime(row.failure.at, KST_ZONE)}
          </p>
        )}
        {row.state === "failed" && (
          <button type="button" onClick={onRetry} className="ml-2 text-xs text-gray-700 underline">다시 시도</button>
        )}
      </td>
      <td data-testid="rate-value" className={`${CELL} font-medium`}>{valueText(row)}</td>
      <td data-testid="rate-change" className={`${CELL} ${rateTone(row.direction)}`}>
        {rateChangeText(row.change, row.direction)}
      </td>
      <td data-testid="rate-date" className={`${CELL} text-gray-700`} title={row.decidedOn ? dottedDate(row.decidedOn) : undefined}>
        {row.decidedOn ? shortDottedDate(row.decidedOn, year) : "—"}
      </td>
    </tr>
  );
}

export function PolicyRateTable() {
  const data = usePolicyRateStore((s) => s.data);
  const status = usePolicyRateStore((s) => s.status);
  const retry = usePolicyRateStore((s) => s.retry);
  const year = kstYear();
  return (
    <section role="region" aria-label="기준금리" data-section="rates">
      <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-gray-700">기준금리</h3>
        <span className="text-xs text-gray-500">결정일은 한국 시간 · 출처 {data?.source ?? "네이버 증권"}</span>
      </div>
      {data && (
        <div className="overflow-x-auto rounded-lg border border-gray-200">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-xs text-gray-500">
                <th scope="col" className="px-3 py-2 text-left font-medium">중앙은행</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">금리</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">전회대비</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">기준 일자</th>
              </tr>
            </thead>
            <tbody>
              {data.banks.map((row) => <RateRow key={row.bank} row={row} year={year} onRetry={() => void retry()} />)}
            </tbody>
          </table>
        </div>
      )}
      {!data && status === "error" && (
        <p role="alert" className="text-sm text-amber-800">기준금리를 불러오지 못했습니다.</p>
      )}
      {!data && status !== "error" && <p className="text-sm text-gray-500">기준금리를 받는 중…</p>}
    </section>
  );
}
