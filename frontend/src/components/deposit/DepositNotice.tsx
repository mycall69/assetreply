"use client";

/**
 * 예금 보드 아래 안내 줄 (T021) — 008 FR-007, FR-016, FR-019, FR-024, SC-005, ui-wireframes D3.
 *
 * - **잠정** — 잠정 시작일, 대신 쓴 금리의 달과 값, "발표되면 값이 바뀐다"를 모두 담는다(SC-005). 하나라도 빠지면 사용자가
 *   잠정 값을 확정 값으로 읽는다. 잠정 회차는 늘 마지막(진행 중) 회차다 — 미발표 달은 마지막 발표 달 뒤에만 있다
 * - **멈춤** — 어느 달이 비어 어느 만기에서 멈췄는지(FR-019). 그날까지의 결과다
 * - **확인 실패** — 오늘 금리를 확인하지 못해 받아 둔 금리로 계산했다는 사실과 사유(FR-016), 인증·형식이면 할 일(FR-016a, 반복 #2)
 *
 * 알림 역할(`role="status"`)이다 — 005~007의 보드 아래 줄과 같다.
 */

import { formatAnnualRate } from "@/lib/format";
import type { DepositFailureKind, DepositSummary } from "@/lib/types";

const LINE = "rounded border px-4 py-2 text-xs";

/**
 * 확인 실패의 할 일(FR-016a, 반복 #2) — 고쳐야 풀리는 종류만 붙인다. 한도 초과·연결 실패는 기다리면 되므로 "내일 다시 확인합니다"로
 * 충분하다. 붙이지 않으면 형식 변경을 기다리면 풀리는 실패로 읽는다.
 */
const RECHECK_ACTION: Partial<Record<DepositFailureKind, string>> = {
  auth: "인증키 설정을 확인하세요.",
  format: "출처의 응답 형식이 바뀌었습니다 — 어댑터를 고쳐야 합니다.",
};

export function DepositNotice({ summary, start }: { summary: DepositSummary; start: string }) {
  const { provisionalFrom, currentTerm, stopped, recheckFailed } = summary;
  return (
    <>
      {provisionalFrom !== null && currentTerm !== null && (
        <p role="status" className={`${LINE} border-sky-200 bg-sky-50 text-sky-900`}>
          ⓘ 잠정 — {provisionalFrom} {provisionalFrom === start ? "가입" : "재예치"} 금리가 아직 발표되지 않아{" "}
          {currentTerm.rateMonth} 금리({formatAnnualRate(currentTerm.rate)})로 계산했습니다. 금리가 발표되면 값이 바뀝니다.
        </p>
      )}
      {stopped !== null && (
        <p role="status" className={`${LINE} border-amber-200 bg-amber-50 text-amber-800`}>
          ⚠ {stopped.month} 금리 통계가 비어 있어 {stopped.date} 만기에서 계산을 멈췄습니다. 그날까지의 결과입니다.
        </p>
      )}
      {recheckFailed !== null && (
        <p role="status" className={`${LINE} border-amber-200 bg-amber-50 text-amber-800`}>
          ⚠ 오늘 금리 확인에 실패했습니다({recheckFailed.reason}) — 받아 둔 금리로 계산했습니다. 내일 다시 확인합니다.
          {RECHECK_ACTION[recheckFailed.kind] !== undefined && ` ${RECHECK_ACTION[recheckFailed.kind]}`}
        </p>
      )}
    </>
  );
}
