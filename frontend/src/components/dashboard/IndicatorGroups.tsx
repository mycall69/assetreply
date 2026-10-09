/**
 * 지표 카드 묶음 (014 T039) — FR-003, contracts D1.
 *
 * 묶음 다섯(한국·미국·일본·중국·환율·원자재·변동성)을 지표의 `order` 차례로 보인다. 카드는 줄바꿈 flex라 좁은 창에서 아래로
 * 감긴다(010 관례 — 경계 상수 없음).
 */
import { IndicatorCard } from "@/components/dashboard/IndicatorCard";
import type { DashboardGroup, DashboardIndicator } from "@/lib/types";

export const GROUP_LABELS: Record<DashboardGroup, string> = {
  korea: "한국",
  us: "미국",
  asia: "일본·중국",
  fx: "환율",
  commodity: "원자재·변동성",
};

export function IndicatorGroups({ indicators, onRetry }: {
  indicators: DashboardIndicator[];
  onRetry: (id: string) => void;
}) {
  const ordered = [...indicators].sort((a, b) => a.order - b.order);
  const groups: DashboardGroup[] = [];
  for (const indicator of ordered) if (!groups.includes(indicator.group)) groups.push(indicator.group);
  return (
    <div className="space-y-5">
      {groups.map((group) => (
        <section key={group} role="region" aria-label={GROUP_LABELS[group]} data-group={group}>
          <h3 className="mb-2 text-sm font-semibold text-gray-700">{GROUP_LABELS[group]}</h3>
          <ul className="flex flex-wrap gap-3">
            {ordered.filter((i) => i.group === group).map((indicator) => (
              <IndicatorCard key={indicator.id} indicator={indicator} onRetry={() => onRetry(indicator.id)} />
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
