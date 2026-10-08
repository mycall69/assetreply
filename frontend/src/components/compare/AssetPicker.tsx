"use client";

/**
 * 비교의 자산군 고르기 (013 T036) — FR-002, ui-wireframes F2.
 *
 * 한 비교에 자산군 하나다. 바꾸면 대상·결과를 비운다(스토어가 한다) — 다른 자산군의 대상이 남으면 그 자산군의 계산 경로로 다른 자산군의
 * 대상을 실행해 엉뚱한 값이 나온다(FR-002 실패 양상).
 */
import { ASSET_LABEL } from "@/lib/compareCondition";
import type { CompareAsset } from "@/lib/types";

const ASSETS: CompareAsset[] = ["stock", "crypto", "deposit", "realestate"];

export function AssetPicker({ value, onChange }: { value: CompareAsset; onChange: (asset: CompareAsset) => void }) {
  return (
    <div role="radiogroup" aria-label="자산군" className="flex flex-wrap items-center gap-x-5 gap-y-2 text-sm">
      <span className="text-gray-500">자산군</span>
      {ASSETS.map((asset) => (
        <label key={asset} className="inline-flex items-center gap-1.5">
          <input type="radio" name="compare-asset" value={asset} checked={value === asset}
            onChange={() => onChange(asset)} />
          {ASSET_LABEL[asset]}
        </label>
      ))}
    </div>
  );
}
