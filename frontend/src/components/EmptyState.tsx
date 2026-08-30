/** 데이터 없음 화면 (T058) — contracts/ui-sketches.md S7. */

export function EmptyState({ onStart }: { onStart?: () => void }) {
  return (
    <section className="rounded-lg border border-dashed border-gray-300 p-12 text-center">
      <p className="text-gray-700">아직 수집된 환율 데이터가 없습니다.</p>
      <p className="mt-2 text-sm text-gray-500">
        전 구간을 처음 수집하는 데 몇 분이 걸립니다. 통화에 따라 60년치가 넘습니다.
      </p>
      {onStart && (
        <button
          type="button"
          onClick={onStart}
          className="mt-6 rounded bg-gray-900 px-5 py-2 text-sm text-white"
        >
          수집 시작
        </button>
      )}
    </section>
  );
}
