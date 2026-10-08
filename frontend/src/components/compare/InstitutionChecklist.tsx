"use client";

/**
 * 예금 투자처 고르기 — 체크박스 (013 T036) — FR-003, FR-004, ui-wireframes F2.
 *
 * 메뉴의 투자처 고르기(`InstitutionPicker`)는 라디오(하나)라 여러 투자처를 고르는 비교에 쓸 수 없다. 정기 적금이면 적금이 없는 투자처를
 * 끈다. 이미 고른 곳은 체크를 남기고 까닭을 보인다 — 몰래 빼지 않는다(실행하면 막힘으로 드러난다 — FR-010).
 */
import { INSTITUTION_KEYS, INSTITUTION_NAMES } from "@/stores/depositStore";
import type { DepositInstitution, DepositInstitutionKey, DepositProduct } from "@/lib/types";

const NO_INSTALLMENT = "정기 적금이 없는 투자처";

export function InstitutionChecklist({ institutions, selected, product, onToggle }: {
  institutions: DepositInstitution[] | null;
  selected: DepositInstitutionKey[];
  product: DepositProduct;
  onToggle: (key: DepositInstitutionKey, checked: boolean) => void;
}) {
  return (
    <fieldset className="text-sm">
      <legend className="mb-1 text-gray-500">투자처</legend>
      <div className="flex flex-wrap items-start gap-x-5 gap-y-2">
        {INSTITUTION_KEYS.map((key) => {
          const info = institutions?.find((i) => i.key === key);
          const noInstallment = product === "installment" && info?.installment !== undefined
            && !info.installment.available;
          const checked = selected.includes(key);
          return (
            <label key={key} className="inline-flex flex-col">
              <span className="inline-flex items-center gap-1.5">
                <input type="checkbox" name="compare-institution" value={key} checked={checked}
                  disabled={noInstallment && !checked} onChange={(e) => onToggle(key, e.target.checked)} />
                {INSTITUTION_NAMES[key]}
              </span>
              {noInstallment && <span className="text-xs text-amber-700">{NO_INSTALLMENT}</span>}
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
