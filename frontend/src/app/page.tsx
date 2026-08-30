"use client";

/** 환율 조회 화면 (US1) — contracts/ui-sketches.md S1·S2·S7. */

import { RateQueryForm } from "@/components/RateQueryForm";
import { RateResult } from "@/components/RateResult";
import { EmptyState } from "@/components/EmptyState";
import { useRateStore } from "@/stores/rateStore";

export default function RateQueryPage() {
  const { result, error } = useRateStore();

  return (
    <div className="space-y-6">
      <RateQueryForm />

      {error && (
        <p role="alert" className="rounded border border-amber-300 bg-amber-50 p-4 text-sm">
          {error}
        </p>
      )}

      {result?.status === "collecting" && (
        <section className="rounded-lg border border-gray-200 p-6">
          <p className="text-gray-700">
            {result.currency} 환율을 수집하고 있습니다. ({result.missingDays}일치)
          </p>
          <p className="mt-2 text-sm text-gray-500">
            완료되면 요청하신 {result.date}의 결과가 표시됩니다.
          </p>
        </section>
      )}

      {(result?.status === "quoted" || result?.status === "no_quote") && (
        <RateResult result={result} />
      )}

      {!result && !error && <EmptyState />}
    </div>
  );
}
