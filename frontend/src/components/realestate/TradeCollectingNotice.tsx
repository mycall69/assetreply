"use client";

/**
 * 실거래 수집 진행 줄 (T026·T039) — 009 FR-011, ui-wireframes E2·E9.
 *
 * 006 `CollectingNotice`를 그대로 쓴다 — 주어 "송파구"·"실거래", 단위 "개월"(008이 더한 선택 속성). 단지 목록(E2)과 실행의 202(E9)가
 * 함께 쓴다. 스냅샷이 오기 전에는 202 본문의 받은 달 / 받을 달을 보인다 — 0/0이나 "시작하는 중"이면 처음 받는 시·군·구의 긴 수집이
 * 멈춘 것처럼 읽힌다.
 */

import { CollectingNotice } from "@/components/stock/CollectingNotice";
import type { RealEstateProgressSnapshot } from "@/lib/realEstateProgressStream";
import type { RealEstateTradeCollecting } from "@/lib/types";

export function TradeCollectingNotice({
  collecting,
  sggName,
  progress,
  doneNote,
}: {
  collecting: RealEstateTradeCollecting;
  /** 받고 있는 시·군·구의 이름 — "송파구". */
  sggName: string | null;
  progress: RealEstateProgressSnapshot | null;
  /** 끝나면 무엇이 달라지는지. 없으면 결과가 표시된다는 말이다. */
  doneNote?: string;
}) {
  const current: RealEstateProgressSnapshot = progress ?? {
    jobId: collecting.jobId, kind: "trade", target: collecting.lawdCd, status: "running",
    done: collecting.monthsDone, total: collecting.monthsTotal,
  };
  return (
    <CollectingNotice collecting={collecting} stockName={sggName ?? "이 시·군·구"} progress={current}
      subject="실거래" unit="개월" doneNote={doneNote} />
  );
}
