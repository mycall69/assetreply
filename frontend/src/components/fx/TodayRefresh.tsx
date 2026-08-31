"use client";

/**
 * 오늘 환율 새로고침 (T069) — contracts/ui-wireframes.md W2·W3-b·W3-c.
 *
 * FR-036: 오늘 하루치만 다시 받는다.
 * FR-040: **실패해도 이미 표시 중인 값을 지우지 않는다.** 실패했다고 화면을 비우면
 * 사용자는 가진 정보까지 잃는다. 사유만 덧붙이고 값은 그대로 둔다.
 */

import { useState } from "react";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type { TodayRefreshResponse } from "@/lib/types";

export function TodayRefresh({
  currency,
  onRefreshed,
}: {
  currency: CurrencyCode;
  onRefreshed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    // 연타해도 호출이 늘지 않게 한다 (SC-008). 서버도 잠금으로 막지만, 굳이
    // 왕복을 만들 이유가 없다.
    if (busy) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await apiClient.post<TodayRefreshResponse>(
        "/api/fx/today/refresh", { currency });
      if (body.status === "no_quote_today") {
        setNotice(body.message ?? "오늘은 아직 고시가 없습니다.");
      }
      onRefreshed();
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "새로고침에 실패했습니다.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="text-right">
      <button
        type="button"
        onClick={() => void refresh()}
        disabled={busy}
        className="rounded border border-gray-300 px-2.5 py-1 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
      >
        ⟳ {busy ? "받는 중…" : "새로고침"}
      </button>
      {notice && <p className="mt-1 text-xs text-gray-500">ⓘ {notice}</p>}
      {error && (
        <p role="alert" className="mt-1 text-xs text-amber-700">
          ⚠ {error} 위 값은 마지막으로 받아온 시점 기준입니다.
        </p>
      )}
    </div>
  );
}
