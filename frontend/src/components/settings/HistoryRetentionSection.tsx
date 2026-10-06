"use client";

/**
 * 설정 — 이력 보관 기간 (012 T058) — FR-012, contracts/ui-wireframes.md F7.
 *
 * - 서버 값을 보이고 선택지는 여섯(7일·30일·90일·180일·365일·무기한)이다. 기본은 30일이다. 네 자산군이 함께 쓴다
 * - 기간을 줄이면 그보다 오래된 항목이 **곧바로** 지워지고 다시 늘려도 돌아오지 않는다 — 칸 곁에 밝힌다(spec Edge Cases). 알리지 않으면 사용자는
 *   잠깐 줄였다 되돌려도 괜찮다고 여긴다
 * - 저장은 `PUT {"retentionDays": …}`이고 무기한은 `null`이다. 성공·실패를 다른 절과 같은 자리에서 알린다(실패는 서버 메시지)
 * - 다른 절과 상태를 공유하지 않는다 — 한쪽의 실패가 다른 쪽을 가리면 무엇이 저장됐는지 알 수 없다(005와 같은 이유)
 */

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/apiClient";
import { fetchRetention, saveRetention } from "@/lib/historyApi";

const OPTIONS: Array<{ value: string; days: number | null; label: string }> = [
  { value: "7", days: 7, label: "7일" },
  { value: "30", days: 30, label: "30일" },
  { value: "90", days: 90, label: "90일" },
  { value: "180", days: 180, label: "180일" },
  { value: "365", days: 365, label: "365일" },
  { value: "unlimited", days: null, label: "무기한" },
];

const valueOf = (days: number | null): string => (days === null ? "unlimited" : String(days));

export function HistoryRetentionSection() {
  const [chosen, setChosen] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        setChosen(valueOf((await fetchRetention()).retentionDays));
      } catch (err) {
        setFailure(err instanceof ApiError ? err.message : "이력 보관 기간을 불러오지 못했습니다.");
      }
    })();
  }, []);

  const save = async () => {
    const option = OPTIONS.find((o) => o.value === chosen);
    if (option === undefined) return;
    try {
      setChosen(valueOf((await saveRetention(option.days)).retentionDays));
      setNotice("저장했습니다. 기간이 지난 항목은 곧바로 지웠습니다.");
      setFailure(null);
    } catch (err) {
      setNotice(null);
      setFailure(err instanceof ApiError ? err.message : "이력 보관 기간을 저장하지 못했습니다.");
    }
  };

  return (
    <div className="space-y-2">
      <h2 className="text-xl font-bold tracking-tight">최근 시뮬레이션 이력</h2>
      {failure !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {failure}
        </p>
      )}
      {notice !== null && <p className="text-sm text-gray-600">{notice}</p>}
      {chosen !== null && (
        <section className="space-y-3 rounded-lg border border-gray-200 p-4 text-sm">
          <label className="flex flex-wrap items-center gap-2">
            <span className="w-24 text-gray-500">보관 기간</span>
            <select aria-label="보관 기간" value={chosen} onChange={(e) => setChosen(e.target.value)}
              className="rounded border border-gray-300 px-2 py-1.5">
              {OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
            </select>
          </label>
          <p className="text-xs text-gray-500">
            ⓘ 마지막 실행 뒤 이 기간이 지난 항목은 지워집니다. 기간을 줄이면 그보다 오래된 항목이 곧바로 지워지고, 다시 늘려도 돌아오지 않습니다.
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button type="button" onClick={() => void save()} className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
              저장
            </button>
            <span className="text-xs text-gray-500">기본값: 30일</span>
          </div>
        </section>
      )}
    </div>
  );
}
