"use client";

/**
 * 수익률 그래프의 확대 단추 (014 반복 2026-10-11b) — spec FR-037, contracts D16.
 *
 * 그래프 칸의 **오른쪽 위**다. 처음에는 그리지 않는다. 시작 지점을 고른 뒤에는 상태 줄(`시작 … · 끝 지점을 누르세요`)과 [취소], 확대된
 * 동안에는 [리셋](처음 전체 범위로)이다 — 확대된 채 다시 고르는 동안에는 둘 다다. 차트 칸 위 층이라 누를 수 있다(커서 상자는
 * `pointer-events: none`). 차트 칸의 누르기 처리기 밖(형제)이라 이 단추를 누른 것이 지점이 되지 않는다.
 */
import type { ZoomState } from "@/lib/chartZoom";

const BUTTON = "rounded border border-gray-300 bg-white px-2 py-0.5 text-xs text-gray-700 hover:bg-gray-50";

export function ChartZoomControls({ state, onCancel, onReset }: {
  state: ZoomState;
  onCancel: () => void;
  onReset: () => void;
}) {
  if (state.kind === "idle") return null;
  const zoomed = state.kind === "zoomed" || state.zoomed !== null;
  return (
    <div className="absolute right-2 top-2 z-20 flex items-center gap-2 text-xs">
      {state.kind === "picking" && (
        <p role="status" data-testid="chart-zoom-status"
          className="flex items-center gap-2 rounded border border-gray-200 bg-white/95 px-2 py-1 text-gray-700 shadow-sm">
          <span>시작 {state.start} · 끝 지점을 누르세요</span>
          <button type="button" onClick={onCancel} className={BUTTON}>취소</button>
        </p>
      )}
      {zoomed && (
        <button type="button" onClick={onReset} title="처음 범위로 되돌립니다" className={`${BUTTON} shadow-sm`}>리셋</button>
      )}
    </div>
  );
}
