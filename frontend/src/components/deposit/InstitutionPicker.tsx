"use client";

/**
 * 투자처 고르기 (T021) — 008 FR-003, FR-006, ui-wireframes D1·D2·접근성.
 *
 * 종목 검색 대신 **라디오 버튼 다섯**이다. `fieldset`·`legend`("투자처")로 묶고 각 항목의 설명을 `aria-describedby`로 잇는다.
 * 방향키 이동은 브라우저의 라디오 묶음 동작(같은 `name`)이다. 이름은 고정이라 목록을 받기 전에도 그린다 — 설명과 시작 가능
 * 달만 서버가 준다. **시작 가능 달은 받아 둔 범위로만 말한다**(research R8-12) — 받기 전에는 모른다고 지어내지 않는다.
 *
 * 011 — 상품이 정기 적금이면(선택 속성 `product`) 출처에 적금 항목이 없는 투자처는 `disabled`이고 사유를 `aria-describedby`로
 * 잇는다(FR-029). 고른 투자처의 설명 줄은 적금 상품 범위와 시작 가능 날짜다. 기본(정기예금)은 지금 동작 그대로다.
 */

import { INSTITUTION_KEYS, INSTITUTION_NAMES } from "@/stores/depositStore";
import type { DepositInstitution, DepositInstitutionKey, DepositProduct } from "@/lib/types";

const NOTE_ID = "deposit-institution-note";

/** 고른 투자처의 설명 줄. 적금이면 적금 상품 범위와 시작 가능 날짜(받은 뒤에만)다. */
function noteFor(selected: DepositInstitution | undefined, product: DepositProduct): string | null {
  if (selected === undefined) return null;
  if (product === "installment") {
    const installment = selected.installment;
    if (installment === undefined) return null;
    if (!installment.available) return installment.reason;
    return installment.startableFrom === null ? installment.description
      : `${installment.description} · ${installment.startableFrom}부터 가입할 수 있습니다`;
  }
  return selected.firstMonth === null ? selected.description
    : `${selected.description} · ${selected.firstMonth}부터`;
}

export function InstitutionPicker({
  institutions,
  value,
  product = "deposit",
  onChange,
}: {
  institutions: DepositInstitution[] | null;
  value: DepositInstitutionKey;
  /** 011 — 정기 적금이면 적금이 없는 투자처를 막는다. 기본은 정기예금(지금 동작)이다. */
  product?: DepositProduct;
  onChange: (key: DepositInstitutionKey) => void;
}) {
  const byKey = new Map((institutions ?? []).map((i) => [i.key, i]));
  const note = noteFor(byKey.get(value), product);

  return (
    <fieldset className="text-sm">
      <legend className="float-left mr-4 py-0.5 text-gray-500">투자처</legend>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {INSTITUTION_KEYS.map((key) => {
          const known = byKey.get(key);
          const installment = known?.installment;
          // 적금이 없는 투자처는 고를 수 없다 — 사유를 설명으로 잇는다(정기예금 금리로 대신하지 않는다).
          const unavailable = product === "installment" && installment !== undefined && !installment.available;
          const description = product !== "installment" ? known?.description
            : installment === undefined ? undefined
              : installment.available ? installment.description : installment.reason;
          // 고른 항목은 아래의 보이는 설명 줄을, 나머지는 숨긴 설명을 잇는다 — 같은 글이 두 번 읽히지 않게 한다.
          const describedBy = description === undefined ? undefined
            : key === value ? NOTE_ID : `deposit-inst-${key}`;
          // 숨긴 설명은 `label` 밖에 둔다 — 안에 두면 항목의 이름에 섞여 읽힌다.
          return (
            <span key={key}>
              <label className={`inline-flex items-center gap-1.5 ${unavailable ? "text-gray-400" : ""}`}>
                <input
                  type="radio"
                  name="deposit-institution"
                  value={key}
                  checked={value === key}
                  disabled={unavailable}
                  onChange={() => onChange(key)}
                  aria-describedby={describedBy}
                />
                {INSTITUTION_NAMES[key]}
              </label>
              {description !== undefined && key !== value && (
                <span id={`deposit-inst-${key}`} className="sr-only">{description}</span>
              )}
            </span>
          );
        })}
      </div>
      {note !== null && <p id={NOTE_ID} className="clear-left mt-1 text-xs text-gray-500">{note}</p>}
    </fieldset>
  );
}
