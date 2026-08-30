"use client";

/** 추이 차트 페이지 (US3) — contracts/ui-sketches.md S3. */

import { useRouter } from "next/navigation";
import { ChartPeriodSelector } from "@/components/ChartPeriodSelector";
import { FxChart } from "@/components/FxChart";
import { useChartStore } from "@/stores/chartStore";

export default function ChartPage() {
  const router = useRouter();
  const { data, collecting, loading, error } = useChartStore();

  return (
    <div className="space-y-6">
      <ChartPeriodSelector />

      {error && (
        <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          {error}
        </p>
      )}

      {collecting && (
        <section className="rounded-lg border border-gray-200 p-6">
          <p className="text-gray-700">
            {collecting.currency} 환율을 수집하고 있습니다. ({collecting.missingDays}일치)
          </p>
          <p className="mt-2 text-sm text-gray-500">완료되면 차트가 표시됩니다.</p>
        </section>
      )}

      {loading && <p className="text-sm text-gray-500">불러오는 중…</p>}

      {data && <FxChart data={data} onSelectDate={() => router.push("/")} />}

      {!data && !collecting && !loading && !error && (
        <p className="text-sm text-gray-500">통화와 기간을 선택한 뒤 조회를 누르세요.</p>
      )}
    </div>
  );
}
