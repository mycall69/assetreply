"use client";

/**
 * 검색 결과 줄의 상장일 조각 (014 반복 2026-10-10f — FR-033, contracts D12). 주식·코인 검색이 함께 쓴다.
 *
 * ` · 상장 1975-06-11`처럼 기준을 밝힌 글자이고, 마우스를 올리면 그 기준의 설명이다. 모르면 아무것도 그리지 않는다(줄은 그대로).
 * 고른 줄 밑 한 줄(`SelectedListingLine` — 반복 2026-10-10g)도 여기다.
 */

import { useSelectedListing } from "@/hooks/useSelectedListing";
import { selectedListingLabel, type ListingLabel } from "@/lib/listingDate";

export function ListingText({ label }: { label: ListingLabel | null }) {
  if (label === null) return null;
  return <span title={label.title}> · {label.text}</span>;
}

/**
 * 고른 줄 밑 한 줄의 상장일 (반복 2026-10-10g — FR-034, contracts D13). 주식·코인 검색이 고른 줄 **아래**에 둔다 — 종목명 밑이다.
 *
 * 묻는 동안·실패면 그리지 않는다(표시 전용 — 검색·고르기·실행은 그대로다). 모르면 `상장일 —`와 까닭이다.
 */
export function SelectedListingLine({ path, refresh, asset, testId }: {
  path: string;
  refresh?: string;
  asset: "stock" | "coin";
  testId: string;
}) {
  const found = useSelectedListing(path, refresh);
  if (found.state === "loading" || found.state === "failed") return null;
  const label = selectedListingLabel(found.state === "known" ? found.listing : null, asset);
  return (
    <p data-testid={testId} className="pl-14 text-xs text-gray-500">
      <span title={label.title}>{label.text}</span>
    </p>
  );
}
