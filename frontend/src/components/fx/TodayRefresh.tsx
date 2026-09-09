"use client";

/**
 * 오늘 환율 새로고침 (T069) — contracts/ui-wireframes.md W2·W3-b·W3-c.
 *
 * FR-036: 오늘 하루치만 다시 받는다.
 * FR-036c: **요청은 시작 시점의 통화에 귀속된다.** 응답이 늦게 도착했을 때 사용자가 이미
 * 통화를 바꿨다면 그 결과를 화면에 반영하지 않는다. 반영하면 USD 새로고침 결과가 JPY
 * 화면에 뜬다.
 * FR-040: **실패해도 이미 표시 중인 값을 지우지 않는다.** 실패했다고 화면을 비우면
 * 사용자는 가진 정보까지 잃는다. 사유만 덧붙이고 값은 그대로 둔다.
 */

import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type { TodayRefreshResponse } from "@/lib/types";

/** 안내 문구는 어느 통화의 것인지와 함께 보관한다 (FR-036c). */
interface Message {
  currency: CurrencyCode;
  text: string;
}

export function TodayRefresh({
  currency,
  onRefreshed,
}: {
  currency: CurrencyCode;
  onRefreshed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Message | null>(null);
  const [error, setError] = useState<Message | null>(null);

  // 응답이 도착한 시점의 "현재 통화". 클로저에 담긴 요청 시점 통화와 비교한다 (FR-036c).
  const shownCurrency = useRef(currency);
  useEffect(() => {
    shownCurrency.current = currency;
  }, [currency]);

  // 안내·오류는 어느 통화의 것인지 함께 들고 다닌다. 통화가 바뀌면 자연히 표시되지 않으므로
  // 효과 안에서 상태를 지울 필요가 없다.
  const visibleNotice = notice?.currency === currency ? notice.text : null;
  const visibleError = error?.currency === currency ? error.text : null;

  const refresh = async () => {
    // 연타해도 호출이 늘지 않게 한다 (SC-008). 서버도 잠금으로 막지만, 굳이
    // 왕복을 만들 이유가 없다.
    if (busy) return;
    const requested = currency;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const body = await apiClient.post<TodayRefreshResponse>(
        "/api/fx/today/refresh", { currency: requested });
      // 기다리는 동안 통화가 바뀌었다면 이 결과는 이 화면의 것이 아니다 (FR-036c).
      if (shownCurrency.current !== requested) return;
      if (body.status === "no_quote_today") {
        setNotice({ currency: requested, text: body.message ?? "오늘은 아직 고시가 없습니다." });
      }
      onRefreshed();
    } catch (err) {
      if (shownCurrency.current !== requested) return;
      setError({
        currency: requested,
        text: err instanceof ApiError ? err.message : "새로고침에 실패했습니다.",
      });
    } finally {
      // 통화가 바뀌었어도 busy는 반드시 푼다. 남으면 새 통화로 다시 받을 수 없다.
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
      {visibleNotice && <p className="mt-1 text-xs text-gray-500">ⓘ {visibleNotice}</p>}
      {visibleError && (
        <p role="alert" className="mt-1 text-xs text-amber-700">
          ⚠ {visibleError} 위 값은 마지막으로 받아온 시점 기준입니다.
        </p>
      )}
    </div>
  );
}
