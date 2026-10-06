"use client";

/**
 * 예금 상품 고르기 (011 T049) — FR-022, ui-wireframes §7.
 *
 * "상품" `fieldset`에 라디오 둘(정기예금 · 정기 적금)이다. 기본은 정기예금이다 — 011 전과 같은 화면으로 열린다(FR-039).
 * 방향키 이동은 브라우저의 라디오 묶음 동작(같은 `name`)이다. 상품을 바꾸면 결과가 빈다(스토어가 한다).
 */

import type { DepositProduct } from "@/lib/types";

const PRODUCTS: { key: DepositProduct; name: string }[] = [
  { key: "deposit", name: "정기예금" },
  { key: "installment", name: "정기 적금" },
];

export function ProductPicker({
  value,
  disabled = false,
  onChange,
}: {
  value: DepositProduct;
  disabled?: boolean;
  onChange: (product: DepositProduct) => void;
}) {
  return (
    <fieldset className="text-sm">
      <legend className="float-left mr-4 py-0.5 text-gray-500">상품</legend>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {PRODUCTS.map((p) => (
          <label key={p.key} className="inline-flex items-center gap-1.5">
            <input type="radio" name="deposit-product" value={p.key} checked={value === p.key}
              disabled={disabled} onChange={() => onChange(p.key)} />
            {p.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
