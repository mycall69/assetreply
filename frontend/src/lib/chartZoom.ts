/**
 * 수익률 그래프의 두 지점 확대 — 순수 규칙 (014 반복 2026-10-11b) — spec FR-037, data-model 15, research R14-30.
 *
 * 상태는 셋이다 — 처음(`idle`), 시작 지점을 고름(`picking`), 확대됨(`zoomed`). 확대된 채 고르면 그 범위를 `zoomed`에 기억해, 취소하면
 * 그 확대로 돌아간다(처음 범위로 튀지 않는다). 두 날은 앞뒤 차례와 무관하게 정렬하고 양 끝을 포함한다. 같은 날을 다시 누르면 취소다.
 * 날짜는 `YYYY-MM-DD` 글자라 글자 차례가 날짜 차례다 — 날짜를 계산하지 않는다.
 */

export interface ZoomRange {
  from: string;
  to: string;
}

export type ZoomState =
  | { kind: "idle" }
  | { kind: "picking"; start: string; zoomed: ZoomRange | null }
  | { kind: "zoomed"; range: ZoomRange };

export const IDLE: ZoomState = { kind: "idle" };

/** 눌렀다 뗀 사이 이만큼 넘게 움직이면 끌기(라이브러리의 옮기기)다 — 누르기로 세지 않는다. */
export const DRAG_TOLERANCE_PX = 4;

export function isDrag(down: { x: number; y: number }, up: { x: number; y: number }): boolean {
  return Math.hypot(up.x - down.x, up.y - down.y) > DRAG_TOLERANCE_PX;
}

export function orderRange(a: string, b: string): ZoomRange {
  return a <= b ? { from: a, to: b } : { from: b, to: a };
}

/** 고르기 전 상태 — 확대된 채 골랐으면 그 확대, 아니면 처음. */
function before(state: Extract<ZoomState, { kind: "picking" }>): ZoomState {
  return state.zoomed === null ? IDLE : { kind: "zoomed", range: state.zoomed };
}

/** 한 날을 눌렀다. 고르는 중에 다른 날이면 확대, 같은 날이면 취소, 아니면 그 날이 시작 지점이다. */
export function pickPoint(state: ZoomState, date: string): ZoomState {
  if (state.kind === "picking") {
    return date === state.start ? before(state) : { kind: "zoomed", range: orderRange(state.start, date) };
  }
  return { kind: "picking", start: date, zoomed: state.kind === "zoomed" ? state.range : null };
}

export function cancelPick(state: ZoomState): ZoomState {
  return state.kind === "picking" ? before(state) : state;
}
