"use client";

/**
 * 투자처 고르기 (T021) — 008 FR-003, FR-006, ui-wireframes D1·D2·접근성.
 *
 * 종목 검색 대신 **라디오 버튼 다섯**이다. `fieldset`·`legend`("투자처")로 묶고 각 항목의 설명을 `aria-describedby`로 잇는다.
 * 방향키 이동은 브라우저의 라디오 묶음 동작(같은 `name`)이다. 이름은 고정이라 목록을 받기 전에도 그린다 — 설명과 시작 가능
 * 달만 서버가 준다. **시작 가능 달은 받아 둔 범위로만 말한다**(research R8-12) — 받기 전에는 모른다고 지어내지 않는다.
 */

import { INSTITUTION_KEYS, INSTITUTION_NAMES } from "@/stores/depositStore";
import type { DepositInstitution, DepositInstitutionKey } from "@/lib/types";

const NOTE_ID = "deposit-institution-note";

export function InstitutionPicker({
  institutions,
  value,
  onChange,
}: {
  institutions: DepositInstitution[] | null;
  value: DepositInstitutionKey;
  onChange: (key: DepositInstitutionKey) => void;
}) {
  const byKey = new Map((institutions ?? []).map((i) => [i.key, i]));
  const selected = byKey.get(value);
  const note = selected === undefined ? null
    : selected.firstMonth === null ? selected.description
      : `${selected.description} · ${selected.firstMonth}부터`;

  return (
    <fieldset className="text-sm">
      <legend className="float-left mr-4 py-0.5 text-gray-500">투자처</legend>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
        {INSTITUTION_KEYS.map((key) => {
          const description = byKey.get(key)?.description;
          // 고른 항목은 아래의 보이는 설명 줄을, 나머지는 숨긴 설명을 잇는다 — 같은 글이 두 번 읽히지 않게 한다.
          const describedBy = description === undefined ? undefined
            : key === value ? NOTE_ID : `deposit-inst-${key}`;
          // 숨긴 설명은 `label` 밖에 둔다 — 안에 두면 항목의 이름에 섞여 읽힌다.
          return (
            <span key={key}>
              <label className="inline-flex items-center gap-1.5">
                <input
                  type="radio"
                  name="deposit-institution"
                  value={key}
                  checked={value === key}
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
