"use client";

/** 스프레드 설정 페이지 (US2) — contracts/ui-sketches.md S5. */

import { useEffect, useState } from "react";
import { SpreadSettings } from "@/components/SpreadSettings";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type { DerivedRates, SpreadRow } from "@/lib/types";

export default function SpreadsPage() {
  const [rows, setRows] = useState<SpreadRow[] | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void apiClient
      .get<{ spreads: SpreadRow[] }>("/api/fx/spreads")
      .then((body) => setRows(body.spreads))
      .catch((err: unknown) =>
        setMessage(err instanceof ApiError ? err.message : "설정을 불러오지 못했습니다."),
      );
  }, []);

  const handleSave = (currency: CurrencyCode, values: DerivedRates) => {
    void apiClient
      .put(`/api/fx/spreads/${currency}`, values)
      .then(() => setMessage(`${currency} 스프레드를 저장했습니다.`))
      .catch((err: unknown) =>
        setMessage(err instanceof ApiError ? err.message : "저장에 실패했습니다."),
      );
  };

  if (!rows) {
    return <p className="text-sm text-gray-500">{message ?? "불러오는 중…"}</p>;
  }

  return (
    <div className="space-y-4">
      <SpreadSettings rows={rows} onSave={handleSave} />
      {message && <p className="text-sm text-gray-600">{message}</p>}
    </div>
  );
}
