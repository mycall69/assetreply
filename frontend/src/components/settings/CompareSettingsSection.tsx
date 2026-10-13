"use client";

/**
 * 설정 — 투자 비교 (014 반복 2026-10-13 T217) — spec FR-044, contracts A18, ui-wireframes D19.
 *
 * - 투자 비교의 **최대 대상 수**(더하기 한도)다. 정수 2~100, 기본 20 — 범위·기본·안내 숫자는 서버 값이다(화면에 박지 않는다). 013 FR-004의 10개를 대체한다
 * - 저장은 `PUT {"maxTargets": <정수>}`이다. 정수가 아니거나 범위 밖이면 요청 없이 칸 오류다. 서버가 거절하면 그 메시지이고, 실패해도 칸 값은 사용자가
 *   친 그대로다(다시 고칠 수 있게)
 * - 저장한 값은 투자 비교 화면을 다시 열 때부터 쓴다(화면이 열 때마다 읽는다). 서버 검증의 끝(100)은 이것과 따로다 — 설정을 낮춰도 저장한 비교는
 *   불러와 실행된다(FR-045)
 * - 다른 절과 상태를 공유하지 않는다 — 한쪽의 실패가 다른 쪽을 가리면 무엇이 저장됐는지 알 수 없다(005와 같은 이유)
 */

import { useEffect, useState } from "react";
import { ApiError } from "@/lib/apiClient";
import { fetchCompareSettings, saveCompareSettings } from "@/lib/compareApi";
import type { CompareSettings } from "@/lib/types";

const INTEGER = /^[0-9]+$/;

export function CompareSettingsSection() {
  const [settings, setSettings] = useState<CompareSettings | null>(null);
  const [typed, setTyped] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    void (async () => {
      try {
        const body = await fetchCompareSettings();
        setSettings(body);
        setTyped(String(body.maxTargets));
      } catch (err) {
        setFailure(err instanceof ApiError ? err.message : "투자 비교 설정을 불러오지 못했습니다.");
      }
    })();
  }, []);

  const save = async () => {
    if (settings === null) return;
    const text = typed.trim();
    const value = INTEGER.test(text) ? Number(text) : null;
    if (value === null || value < settings.minTargets || value > settings.limitTargets) {
      setFieldError(`${settings.minTargets}~${settings.limitTargets} 사이의 정수여야 합니다`);
      setNotice(null);
      return;
    }
    setFieldError(null);
    try {
      const body = await saveCompareSettings(value);
      setSettings(body);
      setTyped(String(body.maxTargets));
      setNotice("저장했습니다. 투자 비교 화면을 다시 열면 새 한도로 더할 수 있습니다.");
      setFailure(null);
    } catch (err) {
      setNotice(null);
      setFailure(err instanceof ApiError ? err.message : "투자 비교 설정을 저장하지 못했습니다.");
    }
  };

  return (
    <div className="space-y-2">
      <h2 className="text-xl font-bold tracking-tight">투자 비교</h2>
      {failure !== null && (
        <p role="alert" className="rounded border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
          {failure}
        </p>
      )}
      {notice !== null && <p className="text-sm text-gray-600">{notice}</p>}
      {settings !== null && (
        <section className="space-y-3 rounded-lg border border-gray-200 p-4 text-sm">
          <label className="flex flex-wrap items-center gap-2">
            <span className="w-24 text-gray-500">최대 대상 수</span>
            <input type="text" inputMode="numeric" aria-label="최대 대상 수" value={typed}
              aria-invalid={fieldError !== null}
              onChange={(e) => {
                setTyped(e.target.value);
                setFieldError(null);
              }}
              className="w-24 rounded border border-gray-300 px-2 py-1.5 text-right tabular-nums" />
            <span className="text-gray-500">개</span>
          </label>
          {fieldError !== null && (
            <p role="alert" className="text-xs text-red-700">{fieldError}</p>
          )}
          <p className="text-xs text-gray-500">
            ⓘ 기본 {settings.defaultMaxTargets}개 · {settings.minTargets}~{settings.limitTargets}개 · 예금은 투자처가 다섯이라 5개까지
          </p>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button type="button" onClick={() => void save()} className="rounded bg-gray-900 px-4 py-2 text-sm text-white">
              저장
            </button>
            <span className="text-xs text-gray-500">기본값: {settings.defaultMaxTargets}개</span>
          </div>
        </section>
      )}
    </div>
  );
}
