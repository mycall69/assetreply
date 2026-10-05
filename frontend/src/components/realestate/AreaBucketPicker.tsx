"use client";

/**
 * 평형 고르기 (T026) — 009 FR-004, ui-wireframes E1·E2·접근성.
 *
 * **라디오 일곱**을 `fieldset`·`legend`("평형")로 묶고 각 항목에 해제를 뺀 거래 수를 보인다. 거래가 0인 구분은 **비활성**과 글자
 * "거래 없음"이다 — 고를 수 있으면 시세가 없는 구분을 실행한다. 각 항목의 경계 줄을 `aria-describedby`로 잇고, 고른 구분은 아래에
 * 경계와 첫 거래 달을 한 줄로 보인다. "전용면적 경계"는 일곱 구분의 경계표를 펼친다.
 *
 * 경계는 서버가 준 구분에서 만든다 — 아래 경계의 포함 여부는 오지 않지만 구분이 빈틈없이 이어지므로 앞 구분의 위 경계와 반대다.
 * 실거래를 다 받기 전에는 거래 수를 모른다 — 0건이나 "거래 없음"으로 보이면 거래가 없는 단지로 읽으므로 안내만 보인다(E2).
 */

import { useState } from "react";
import type { RealEstateAreaBucket, RealEstateAreaKey, RealEstateAreasResponse } from "@/lib/types";

const NOTE_ID = "realestate-area-note";
const TABLE_ID = "realestate-area-boundaries";

/** 구분의 전용면적 범위 — "70㎡ 이상 85㎡ 이하". 첫 구분은 아래 경계가, 마지막 구분은 위 경계가 없다. */
export function bucketRange(buckets: RealEstateAreaBucket[], index: number): string {
  const bucket = buckets[index];
  const previous = index > 0 ? buckets[index - 1] : null;
  const parts: string[] = [];
  // 앞 구분이 위 경계를 포함하면(85㎡ 이하) 이 구분은 그 값을 넘어서부터다(85㎡ 초과).
  if (bucket.minArea !== null) parts.push(`${bucket.minArea}㎡ ${previous?.maxInclusive ? "초과" : "이상"}`);
  if (bucket.maxArea !== null) parts.push(`${bucket.maxArea}㎡ ${bucket.maxInclusive ? "이하" : "미만"}`);
  return parts.join(" ");
}

export function AreaBucketPicker({
  areas,
  value,
  onChange,
  waitingForTrades,
}: {
  /** 단지를 고르기 전·받기 전에는 `null`이다. */
  areas: RealEstateAreasResponse | null;
  value: RealEstateAreaKey | null;
  onChange: (key: RealEstateAreaKey) => void;
  /** 그 시·군·구의 실거래를 아직 다 받지 않았다(수집 중·실패·평형 202). */
  waitingForTrades: boolean;
}) {
  const [open, setOpen] = useState(false);
  const buckets = waitingForTrades || areas === null ? null : areas.buckets;
  const selectedIndex = buckets === null ? -1 : buckets.findIndex((b) => b.key === value);
  const selected = buckets !== null && selectedIndex >= 0 ? buckets[selectedIndex] : null;
  const note = buckets === null || selected === null ? null
    : `${selected.label} — 전용 ${bucketRange(buckets, selectedIndex)}`
      + (selected.firstMonth === null ? "" : ` · ${selected.firstMonth}부터`);

  return (
    <fieldset className="text-sm">
      <legend className="float-left mr-4 w-10 py-0.5 text-gray-500">평형</legend>
      {buckets === null ? (
        <p className="py-0.5 text-gray-500">
          {waitingForTrades ? "실거래를 받은 뒤 고를 수 있습니다" : "단지를 고른 뒤 고를 수 있습니다"}
        </p>
      ) : (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {buckets.map((bucket, index) => {
            const empty = bucket.trades === 0;
            // 고른 항목은 아래의 보이는 줄을, 나머지는 숨긴 경계 줄을 잇는다 — 같은 글이 두 번 읽히지 않게 한다.
            const describedBy = bucket.key === value ? NOTE_ID : `realestate-area-${bucket.key}`;
            return (
              <span key={bucket.key}>
                <label className={`inline-flex items-center gap-1.5 ${empty ? "text-gray-400" : ""}`}>
                  <input
                    type="radio"
                    name="realestate-area"
                    value={bucket.key}
                    checked={value === bucket.key}
                    disabled={empty}
                    onChange={() => onChange(bucket.key)}
                    aria-describedby={describedBy}
                  />
                  <span>{bucket.label}</span>{" "}
                  <span className="tabular-nums text-gray-500">
                    {empty ? "거래 없음" : `${bucket.trades.toLocaleString("ko-KR")}건`}
                  </span>
                </label>
                {/* 숨긴 설명은 `label` 밖에 둔다 — 안에 두면 항목의 이름에 섞여 읽힌다. */}
                {bucket.key !== value && (
                  <span id={`realestate-area-${bucket.key}`} className="sr-only">
                    전용 {bucketRange(buckets, index)}
                    {bucket.firstMonth === null ? "" : ` · ${bucket.firstMonth}부터`}
                  </span>
                )}
              </span>
            );
          })}
          <button
            type="button"
            aria-expanded={open}
            aria-controls={TABLE_ID}
            onClick={() => setOpen(!open)}
            className="text-xs text-gray-500 underline-offset-2 hover:underline"
          >
            ⓘ 전용면적 경계
          </button>
        </div>
      )}
      {note !== null && <p id={NOTE_ID} className="clear-left mt-1 text-xs text-gray-500">{note}</p>}
      {buckets !== null && open && (
        <table id={TABLE_ID} className="clear-left mt-2 text-xs">
          <thead>
            <tr className="text-left text-gray-500">
              <th scope="col" className="pr-6 font-normal">평형 구분</th>
              <th scope="col" className="font-normal">전용면적</th>
            </tr>
          </thead>
          <tbody>
            {buckets.map((bucket, index) => (
              <tr key={bucket.key}>
                <td className="pr-6">{bucket.label}</td>
                <td className="tabular-nums">{bucketRange(buckets, index)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </fieldset>
  );
}
