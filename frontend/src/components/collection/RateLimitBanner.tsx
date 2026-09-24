"use client";

/**
 * 호출 한도 소진 배너 (T071) — contracts/ui-wireframes.md W4.
 *
 * **"지금까지 받은 데이터는 그대로 유효합니다"는 FR-026의 요구다.** 이 문장이 없으면
 * 사용자는 한도 소진을 데이터 손실로 오해한다.
 *
 * 한도는 인증 키 단위라 **다른 통화로 전환해도 소진 상태는 그대로다.** 전환하면
 * 풀린다고 오해하면 헛수고를 한다.
 */

import type { CurrencyCode } from "@/lib/types";

export function RateLimitBanner({
  currency,
  coveredThrough,
}: {
  currency: CurrencyCode;
  coveredThrough: string | null;
}) {
  return (
    <div
      role="alert"
      className="rounded border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <p className="font-medium">⚠ 오늘의 호출 한도를 모두 썼습니다</p>
      <p className="mt-1 text-xs text-amber-800">
        {currency} 수집이 {coveredThrough ?? "시작 지점"}까지 받고 멈췄습니다. 지금까지
        받은 데이터는 그대로 유효합니다. 내일 이어받기를 누르면 멈춘 지점부터
        계속됩니다.
      </p>
      <p className="mt-1 text-xs text-amber-700">
        한도는 모든 통화가 함께 씁니다. 다른 통화로 바꿔도 오늘은 시작할 수 없습니다.
      </p>
    </div>
  );
}
