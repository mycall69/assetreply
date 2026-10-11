"use client";

/**
 * 금리 모달의 내용 (014 반복 2026-10-11d T209) — FR-041, FR-042, SC-026, contracts D18.
 *
 * 지표 모달과 같은 껍데기(`IndicatorModal` — 주소 있는 모달·닫기·포커스)에 은행이면 이 내용이다. 머리 → 변화 까닭 → 기간 단추 → 계단선 그래프 →
 * "금리 추이" 표.
 *
 * - 머리: 이름·금리 종류·현재 금리·전회대비·결정일(실제 발표 시각이 있으면 한국 시각)·다음 결정 예정(없으면 뺀다)·저장된 기간·출처. 값은
 *   서버 글자 그대로다(원칙 VI — 칸과 같은 함수의 값)
 * - 기간 단추(1년·5년·10년·모두)는 그래프의 처음 보이는 범위만 바꾸고 주소의 `range`를 바꾼다(`history.replaceState` — 지표 모달과 같다).
 *   금리에 없는 기간의 주소는 1년이다
 * - 처음 받는 중이면 "결정 이력을 받는 중…"(5초 뒤 다시 읽는다), 받아 둔 값 없이 실패면 까닭과 [다시 시도]
 */
import { useEffect, useState } from "react";
import { failureLabel } from "@/components/dashboard/IndicatorHeader";
import { IndicatorCommentary } from "@/components/dashboard/IndicatorCommentary";
import { rateChangeText, rateTone } from "@/components/dashboard/PolicyRateTable";
import { RangePicker } from "@/components/dashboard/RangePicker";
import { RateChart } from "@/components/dashboard/RateChart";
import { RateTable } from "@/components/dashboard/RateTable";
import { KST_ZONE, formatZonedTime } from "@/lib/kstClock";
import { dottedDate, rateRangeOf } from "@/lib/rateFormat";
import { RATE_RANGES, type IndicatorRange, type PolicyRateDetail, type RateRange } from "@/lib/types";
import { usePolicyRateStore, type RateCommentaryEntry, type RateDetailEntry } from "@/stores/policyRateStore";

const LOADING_DETAIL: RateDetailEntry = { status: "loading", body: null };
const LOADING_COMMENTARY: RateCommentaryEntry = { status: "loading", body: null };
const SOURCE = "네이버 증권";

function RateHeader({ detail, name, titleId }: { detail: PolicyRateDetail | null; name: string; titleId?: string }) {
  return (
    <header data-testid="rate-header" className="space-y-2">
      <h2 id={titleId} className="text-2xl font-bold tracking-tight">{name}</h2>
      {detail && (
        <>
          <p className="text-sm text-gray-500">{detail.rateKind}</p>
          {detail.rate !== null && (
            <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
              <span data-testid="rate-header-value" className="text-2xl font-semibold tabular-nums">{detail.rate}%</span>
              <span data-testid="rate-header-change" className={`text-sm tabular-nums ${rateTone(detail.direction)}`}>
                {rateChangeText(detail.change, detail.direction)}
              </span>
              {detail.decidedOn && (
                <span className="text-xs text-gray-500">
                  결정 {dottedDate(detail.decidedOn)}
                  {detail.announcedAt && ` ${formatZonedTime(detail.announcedAt, KST_ZONE)}(한국)`}
                </span>
              )}
              {detail.nextMeetingOn && (
                <span className="text-xs text-gray-500">다음 결정 예정 {dottedDate(detail.nextMeetingOn)}</span>
              )}
            </div>
          )}
          {detail.firstDecidedOn && detail.lastDecidedOn && (
            <p className="text-xs text-gray-500">
              저장된 기간 {dottedDate(detail.firstDecidedOn)} ~ {dottedDate(detail.lastDecidedOn)} · 출처 {SOURCE}
            </p>
          )}
          {detail.rate !== null && detail.failure && (
            <p className="text-xs text-amber-800">
              최근 갱신 실패 — {failureLabel(detail.failure.kind)} · {formatZonedTime(detail.failure.at, KST_ZONE)}
            </p>
          )}
        </>
      )}
    </header>
  );
}

export function RateView({ bank, range, titleId }: {
  bank: string;
  /** 주소의 기간 — 금리에 없는 기간은 1년이다. */
  range: IndicatorRange;
  titleId?: string;
}) {
  const entry = usePolicyRateStore((s) => s.details[bank]) ?? LOADING_DETAIL;
  const commentary = usePolicyRateStore((s) => s.commentary[bank]) ?? LOADING_COMMENTARY;
  const row = usePolicyRateStore((s) => s.data?.banks.find((b) => b.bank === bank) ?? null);
  const openDetail = usePolicyRateStore((s) => s.openDetail);
  const closeDetail = usePolicyRateStore((s) => s.closeDetail);
  const loadCommentary = usePolicyRateStore((s) => s.loadCommentary);
  const retry = usePolicyRateStore((s) => s.retry);
  const [shown, setShown] = useState<RateRange>(() => rateRangeOf(range));

  useEffect(() => {
    void openDetail(bank);
    void loadCommentary(bank);
    return () => closeDetail();
  }, [bank, openDetail, loadCommentary, closeDetail]);

  const detail = entry.body;
  const name = detail?.name ?? row?.name ?? bank;
  const ready = detail !== null && detail.decisions.length > 0;

  return (
    <div className="space-y-4">
      <RateHeader detail={detail} name={name} titleId={titleId} />
      <IndicatorCommentary state={commentary} onRetry={() => void loadCommentary(bank)}
        noneText="최근 결정을 다룬 기사를 찾지 못했습니다" />
      <RangePicker value={shown} ranges={RATE_RANGES} onChange={(next) => {
        const picked = rateRangeOf(next);
        setShown(picked);
        // 주소만 바꾼다 — 모달을 다시 붙이지 않는다(지표 모달과 같다 — T137)
        window.history.replaceState(null, "", `?range=${picked}`);
      }} />
      {ready && (
        <>
          <RateChart decisions={detail.decisions} range={shown} lastDecidedOn={detail.lastDecidedOn} />
          <RateTable decisions={detail.decisions} nextMeetingOn={detail.nextMeetingOn} />
        </>
      )}
      {detail && !ready && detail.state === "failed" && (
        <div role="alert" className="space-y-1 text-sm text-amber-800">
          <p>결정 이력을 받지 못했습니다 — {failureLabel(detail.failure?.kind)}</p>
          <button type="button" onClick={() => void retry()} className="text-gray-700 underline">다시 시도</button>
        </div>
      )}
      {detail && !ready && detail.state !== "failed" && <p className="text-sm text-gray-500">결정 이력을 받는 중…</p>}
      {!detail && entry.status === "loading" && <p className="text-sm text-gray-500">결정 이력을 불러오는 중…</p>}
      {entry.status === "error" && <p role="alert" className="text-sm text-amber-800">결정 이력을 불러오지 못했습니다.</p>}
    </div>
  );
}
