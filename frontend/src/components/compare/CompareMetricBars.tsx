"use client";

/**
 * 최종 지표 막대 (013 T056) — FR-015, SC-005, research R13-12, ui-wireframes F7.
 *
 * 수익률 묶음과 투자 수익 묶음이다. 시계열이 아니라 DOM 막대다(헌법 원칙 VII는 시계열 차트를 Lightweight Charts로 정한다). 글자 값은
 * 서버 문자열을 표와 같은 형식 함수로 보인다 — 값의 진실은 글자다. **막대 길이만 그리기 전용으로 숫자를 쓴다**(차트의
 * `chartSeries.toPerformanceData`와 같은 선례, plan Complexity Tracking). 값이 없으면 막대 없이 "—"다. 차례는 받은 차례(표의 지금 정렬)다.
 * 잠정 입력을 쓴 대상은 이름 곁에 ⏳다(원칙 V).
 */
import { formatMoneyWithSymbol, formatPercent } from "@/lib/format";

export interface MetricItem {
  key: string;
  name: string;
  returnRate: string | null;
  profit: string | null;
  provisional: boolean;
}

/** 그리기 전용 — 막대 길이의 비율. 값의 표시에는 쓰지 않는다. */
const magnitude = (value: string): number => Math.abs(Number(value));

function Group({ title, items, value, format }: {
  title: string;
  items: MetricItem[];
  value: (item: MetricItem) => string | null;
  format: (text: string) => string;
}) {
  const largest = Math.max(0, ...items.flatMap((i) => {
    const v = value(i);
    return v === null ? [] : [magnitude(v)];
  }));
  return (
    <div role="group" aria-label={title} className="space-y-1">
      <p className="text-xs font-semibold text-gray-600">{title}</p>
      <ul className="space-y-1">
        {items.map((item) => {
          const v = value(item);
          const negative = v !== null && v.trimStart().startsWith("-");
          const share = v === null || largest === 0 ? 0 : (magnitude(v) / largest) * 100;
          return (
            <li key={item.key} className="grid grid-cols-[10rem_1fr_8rem] items-center gap-2 text-xs">
              {/* 014 FR-032 — 칸(10rem)보다 긴 이름은 줄어 티커가 가려진다. 마우스를 올리면 전체 이름이다. */}
              <span className="truncate" title={item.name}>{item.provisional ? `${item.name} ⏳` : item.name}</span>
              <span className="grid grid-cols-2">
                <span className="flex justify-end border-r border-gray-300">
                  {v !== null && negative && (
                    <span data-testid="metric-bar" data-sign="negative" className="block h-3 rounded-l bg-blue-500"
                      style={{ width: `${share}%` }} />
                  )}
                </span>
                <span className="flex">
                  {v !== null && !negative && (
                    <span data-testid="metric-bar" data-sign="positive" className="block h-3 rounded-r bg-red-500"
                      style={{ width: `${share}%` }} />
                  )}
                </span>
              </span>
              <span className="text-right tabular-nums">{v === null ? "—" : format(v)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function CompareMetricBars({ items }: { items: MetricItem[] }) {
  return (
    <section className="space-y-4 rounded-lg border border-gray-200 p-4" data-testid="compare-bars">
      <h3 className="text-sm font-semibold">최종 지표 (표와 같은 값)</h3>
      <Group title="수익률" items={items} value={(i) => i.returnRate} format={(t) => formatPercent(t)} />
      <Group title="투자 수익" items={items} value={(i) => i.profit} format={(t) => formatMoneyWithSymbol(t, "KRW")} />
    </section>
  );
}
