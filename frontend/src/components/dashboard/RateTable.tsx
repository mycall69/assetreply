/**
 * 금리 추이 표 (014 반복 2026-10-11d T209) — FR-041, SC-026, contracts D18.
 *
 * 날짜·금리·전회대비. 맨 위는 **다음 결정 예정** 행(날짜 · — · —, 스크린샷과 같다 — 예정일이 없으면 없다), 그 아래는 저장된 결정 **전부**(최신부터 —
 * 은행마다 약 90행, 쪽을 나누지 않고 칸 안에서 세로로 스크롤한다). 금리·전회대비는 서버 글자 그대로다(원칙 VI). 예정 행은 결정이 아니다 —
 * 금리를 0으로 보이지 않는다.
 */
import { rateChangeText, rateTone } from "@/components/dashboard/PolicyRateTable";
import { dottedDate } from "@/lib/rateFormat";
import type { PolicyRateDecision } from "@/lib/types";

const CELL = "whitespace-nowrap px-3 py-1.5 text-right tabular-nums";

export function RateTable({ decisions, nextMeetingOn }: {
  /** 최신부터. */
  decisions: PolicyRateDecision[];
  nextMeetingOn: string | null;
}) {
  return (
    <section data-testid="rate-table" aria-label="금리 추이" className="space-y-2">
      <h3 className="text-sm font-semibold text-gray-900">금리 추이</h3>
      <div className="max-h-[28rem] overflow-auto rounded border border-gray-200">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-xs text-gray-500">
              <th scope="col" className="px-3 py-2 text-left font-medium">날짜</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">금리</th>
              <th scope="col" className="px-3 py-2 text-right font-medium">전회대비</th>
            </tr>
          </thead>
          <tbody>
            {nextMeetingOn && (
              <tr data-testid="rate-table-row" className="border-b border-gray-100 text-gray-500">
                <td className="whitespace-nowrap px-3 py-1.5 text-left tabular-nums">
                  {dottedDate(nextMeetingOn)} <span className="text-xs">(다음 결정 예정)</span>
                </td>
                <td className={CELL}>—</td>
                <td data-testid="rate-table-change" className={CELL}>—</td>
              </tr>
            )}
            {decisions.map((d) => (
              <tr key={d.decidedOn} data-testid="rate-table-row" className="border-b border-gray-100">
                <td className="whitespace-nowrap px-3 py-1.5 text-left tabular-nums text-gray-700">{dottedDate(d.decidedOn)}</td>
                <td className={`${CELL} font-medium`}>{d.rate}</td>
                <td data-testid="rate-table-change" className={`${CELL} ${rateTone(d.direction)}`}>
                  {rateChangeText(d.change, d.direction)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
