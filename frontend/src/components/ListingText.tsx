/**
 * 검색 결과 줄의 상장일 조각 (014 반복 2026-10-10f — FR-033, contracts D12). 주식·코인 검색이 함께 쓴다.
 *
 * ` · 상장 1975-06-11`처럼 기준을 밝힌 글자이고, 마우스를 올리면 그 기준의 설명이다. 모르면 아무것도 그리지 않는다(줄은 그대로).
 */
import type { ListingLabel } from "@/lib/listingDate";

export function ListingText({ label }: { label: ListingLabel | null }) {
  if (label === null) return null;
  return <span title={label.title}> · {label.text}</span>;
}
