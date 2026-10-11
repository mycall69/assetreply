/**
 * 수익률 그래프의 두 지점 확대 — 순수 규칙 (014 반복 2026-10-11b T184) — spec FR-037, SC-022, data-model 15, research R14-30.
 *
 * 상태는 셋이다 — 처음(`idle`), 시작 지점을 고름(`picking` — 확대된 채 고르면 그 범위를 기억한다), 확대됨(`zoomed`). 두 날은 앞뒤 차례와
 * 무관하게 정렬하고 양 끝을 포함한다. 같은 날을 다시 누르거나 취소하면 고르기 전 상태로 돌아간다. 눌렀다 뗀 사이 4px 넘게 움직이면 끌기다.
 */
import { describe, expect, it } from "vitest";
import { DRAG_TOLERANCE_PX, IDLE, cancelPick, isDrag, orderRange, pickPoint } from "@/lib/chartZoom";

describe("두 날", () => {
  it("앞뒤 차례와 무관하게 정렬한다", () => {
    expect(orderRange("2024-09-30", "2024-03-04")).toEqual({ from: "2024-03-04", to: "2024-09-30" });
    expect(orderRange("2024-03-04", "2024-09-30")).toEqual({ from: "2024-03-04", to: "2024-09-30" });
  });
});

describe("상태 전이", () => {
  it("처음에 누르면 시작 지점을 고른다", () => {
    expect(pickPoint(IDLE, "2024-03-04")).toEqual({ kind: "picking", start: "2024-03-04", zoomed: null });
  });

  it("다른 날을 누르면 두 날 사이로 확대된다", () => {
    const picking = pickPoint(IDLE, "2024-09-30");
    expect(pickPoint(picking, "2024-03-04")).toEqual({ kind: "zoomed", range: { from: "2024-03-04", to: "2024-09-30" } });
  });

  it("같은 날을 다시 누르면 고르기를 취소한다", () => {
    expect(pickPoint(pickPoint(IDLE, "2024-03-04"), "2024-03-04")).toEqual(IDLE);
  });

  it("확대된 채 누르면 그 범위를 기억한 채 고른다 — 취소하면 그 확대로 돌아간다", () => {
    const zoomed = pickPoint(pickPoint(IDLE, "2024-01-02"), "2024-12-31");
    const picking = pickPoint(zoomed, "2024-03-04");
    expect(picking).toEqual({ kind: "picking", start: "2024-03-04", zoomed: { from: "2024-01-02", to: "2024-12-31" } });
    expect(cancelPick(picking)).toEqual(zoomed);
    expect(pickPoint(picking, "2024-03-04")).toEqual(zoomed);
  });

  it("확대 안에서 다시 확대할 수 있다", () => {
    const zoomed = pickPoint(pickPoint(IDLE, "2024-01-02"), "2024-12-31");
    expect(pickPoint(pickPoint(zoomed, "2024-05-01"), "2024-04-01"))
      .toEqual({ kind: "zoomed", range: { from: "2024-04-01", to: "2024-05-01" } });
  });

  it("고르는 중이 아니면 취소해도 그대로다", () => {
    expect(cancelPick(IDLE)).toEqual(IDLE);
    const zoomed = pickPoint(pickPoint(IDLE, "2024-01-02"), "2024-12-31");
    expect(cancelPick(zoomed)).toBe(zoomed);
  });
});

describe("끌기", () => {
  it(`${DRAG_TOLERANCE_PX}px 넘게 움직이면 끌기다`, () => {
    expect(DRAG_TOLERANCE_PX).toBe(4);
    expect(isDrag({ x: 100, y: 100 }, { x: 104, y: 100 })).toBe(false);
    expect(isDrag({ x: 100, y: 100 }, { x: 103, y: 103 })).toBe(true);
    expect(isDrag({ x: 100, y: 100 }, { x: 160, y: 100 })).toBe(true);
    expect(isDrag({ x: 100, y: 100 }, { x: 100, y: 100 })).toBe(false);
  });
});
