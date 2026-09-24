"use client";

/**
 * 기록 불완전 경고 (T060) — contracts/ui-wireframes.md W5, FR-018b.
 *
 * **"수집 자체는 정상입니다"를 반드시 함께 표시한다.** 기록 실패와 수집 실패는 다른
 * 일인데, 경고만 보면 사용자가 데이터를 의심하게 된다. FR-018a가 "기록 실패가 수집을
 * 중단시키지 않는다"고 정한 이상, 화면도 둘을 구별해야 한다.
 *
 * `dropped === 0`이면 **아무것도 렌더링하지 않는다.** 정상 상태에 "기록 완전함" 같은
 * 표시를 두면 소음이 된다.
 */

export function IncompleteRecordNotice({ dropped }: { dropped: number }) {
  if (dropped <= 0) return null;

  return (
    <div
      role="alert"
      className="rounded border border-amber-300 bg-amber-50 px-4 py-2 text-xs text-amber-900"
    >
      <p className="font-medium">⚠ 이 작업의 기록 {dropped}건이 저장되지 않았습니다</p>
      <p className="mt-0.5 text-amber-800">
        아래 목록은 완전하지 않습니다. 수집 자체는 정상입니다.
      </p>
    </div>
  );
}
