"use client";

/**
 * 부동산 보드 아래 안내 줄 (T039) — 009 FR-010, FR-014, FR-018, FR-021, FR-026, ui-wireframes E4.
 *
 * 해당할 때만, 이 순서대로 한 줄씩 — 알림 역할(`role="status"`, 005~008과 같다).
 * 1. **잠정** — 잠정 기간(`provisionalFrom`의 달 ~ 오늘의 달)과 "바뀔 수 있다"와 그 이유 둘. 지금 시세가 잠정 거래를 쓸 때다. 기간의
 *    길이는 서버 설정이 정한다 — 화면이 세면 설정을 바꿨을 때 안내가 실제 잠정 기간과 어긋난다
 * 2. **지금 시세 없음** — 마지막으로 시세가 있던 달과 그 달까지의 결과라는 사실(FR-026)
 * 3. **보유세 계산 불가** — 6월 시세가 없어 계산하지 못한 해를 모두(FR-021). 누적 비용이 실제보다 작다
 * 4. **확인 실패** — 받아 둔 거래로 계산했고 내일 다시 확인한다. 고쳐야 풀리는 종류(인증·형식)만 할 일을 붙인다(008 D3과 같다) —
 *    한도 초과·연결 실패는 기다리면 된다
 */

import type { RealEstateFailureKind, RealEstateSummary } from "@/lib/types";

const LINE = "rounded border px-4 py-2 text-xs";
const INFO = `${LINE} border-sky-200 bg-sky-50 text-sky-900`;
const WARN = `${LINE} border-amber-200 bg-amber-50 text-amber-800`;

const RECHECK_ACTION: Partial<Record<RealEstateFailureKind, string>> = {
  auth: "인증키 설정을 확인하세요.",
  format: "출처의 응답 형식이 바뀌었습니다 — 어댑터를 고쳐야 합니다.",
};

export function RealEstateNotice({ summary }: { summary: RealEstateSummary }) {
  const { provisional, provisionalFrom, asOf, value, lastPricedMonth, taxGaps, recheckFailed } = summary;
  const action = recheckFailed === undefined ? undefined : RECHECK_ACTION[recheckFailed.kind];
  return (
    <>
      {provisional && (
        <p role="status" className={INFO}>
          ⓘ 잠정 — {provisionalFrom.slice(0, 7)} ~ {asOf.slice(0, 7)} 거래는 바뀔 수 있습니다(최근 3개월은 신고가 더 들어오고, 그
          앞은 해제가 늦게 반영됩니다). 지금 시세가 이 거래를 씁니다.
        </p>
      )}
      {value === null && (
        <p role="status" className={WARN}>
          ⚠ 지금 시세 없음 — 36개월 안에 거래가 없습니다.{" "}
          {lastPricedMonth === null
            ? "시세가 있던 달이 없어 평가액과 수익을 계산하지 못했습니다."
            : `마지막으로 시세가 있던 ${lastPricedMonth}까지의 결과입니다.`}
        </p>
      )}
      {taxGaps.length > 0 && (
        <p role="status" className={WARN}>
          ⚠ {taxGaps.map((year) => `${year}년`).join("·")} 보유세를 계산하지 못했습니다(6월 시세 없음) — 누적 비용이 실제보다
          작습니다.
        </p>
      )}
      {recheckFailed !== undefined && (
        <p role="status" className={WARN}>
          ⚠ 오늘 실거래 확인에 실패했습니다({recheckFailed.reason}) — 받아 둔 거래로 계산했습니다. 내일 다시 확인합니다.
          {action !== undefined && ` ${action}`}
        </p>
      )}
    </>
  );
}
