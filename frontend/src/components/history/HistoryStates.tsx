/**
 * 이력 칸의 안내와 상태 (012 T057) — FR-014, FR-014a, FR-015, contracts/ui-wireframes.md F6. 이력 부품 넷이 함께 쓴다.
 *
 * - 안내는 보관 위치(이 기기의 로컬 DB)와 보관 기간을 말한다 — 012 전의 "이 브라우저에만 저장됩니다"를 대체한다. 보관 기간을 아직 모르면(목록 전)
 *   기간을 말하지 않는다 — 기본값을 짐작해 적으면 설정과 다른 기간을 말할 수 있다
 * - 불러오는 중에는 빈 상태 문구를 보이지 않는다 — 비어 있는 것으로 오해한다
 * - 불러오기 실패는 알림과 다시 시도 단추다. 빈 상태 문구를 보이지 않는다(FR-014a — 실패가 빈 목록으로 보이면 지워졌다고 오해한다)
 * - 빈 상태 문구는 속성으로 바꿀 수 있다(013 T075 — 저장한 비교 칸). 처음 값은 지금 문구다 — 메뉴 이력 칸은 그대로다
 */

import type { ReactNode } from "react";

/** 이력 부품의 상태 속성 — 모두 선택이다(지금 속성만으로 그려도 그대로다). */
export interface HistoryStateProps {
  loading?: boolean;
  loadError?: string | null;
  onRetry?: () => void;
  /** 옮기지 못한 항목 수 알림. */
  notice?: string | null;
  /** 보관 기간(일). `null`은 무기한, 없으면 아직 모른다. */
  retentionDays?: number | null;
}

export function HistoryNotice({ retentionDays, scope }: { retentionDays?: number | null; scope: string }) {
  const period = retentionDays === undefined ? ""
    : retentionDays === null ? " 기한 없이 남습니다 — 기간은 설정에서 바꿉니다."
      : ` 마지막 실행 뒤 ${retentionDays}일이 지나면 지워집니다 — 기간은 설정에서 바꿉니다.`;
  return (
    <p data-testid="history-notice" className="text-xs text-gray-500">
      {`ⓘ 이 기기의 로컬 DB에 저장됩니다.${period}${scope}`}
    </p>
  );
}

/** 목록 자리 — 알림, 불러오기 실패·불러오는 중·빈 상태, 그리고 목록. */
export function HistoryContent({
  loading = false, loadError = null, onRetry, notice = null, empty, emptyText = "아직 실행한 시뮬레이션이 없습니다.", children,
}: Omit<HistoryStateProps, "retentionDays"> & { empty: boolean; emptyText?: string; children: ReactNode }) {
  return (
    <>
      {notice !== null && (
        <p role="status" className="mb-3 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {notice}
        </p>
      )}
      {loadError !== null && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-xs">
          <p role="alert" className="text-red-700">{loadError}</p>
          {onRetry !== undefined && (
            <button type="button" onClick={onRetry}
              className="rounded border border-red-300 bg-white px-2 py-0.5 text-red-700 hover:bg-red-100">
              다시 시도
            </button>
          )}
        </div>
      )}
      {loading && <p className="py-2 text-center text-sm text-gray-500">⟳ 불러오는 중…</p>}
      {empty
        ? !loading && loadError === null && (
          <p className="py-6 text-center text-sm text-gray-500">{emptyText}</p>
        )
        : children}
    </>
  );
}
