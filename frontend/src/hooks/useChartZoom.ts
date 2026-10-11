"use client";

/**
 * 수익률 그래프의 두 지점 확대 (014 반복 2026-10-11b) — spec FR-037, data-model 15, research R14-30, contracts D16.
 *
 * - 누름은 **차트 칸의 DOM 이벤트**다(잡기 단계 — 라이브러리가 캔버스에서 전파를 막아도 받는다). 눌렀다 뗀 사이 4px 넘게 움직였으면
 *   끌기(라이브러리의 옮기기)라 세지 않는다
 * - 누른 날짜는 커서를 쫓는 그래프면 `track`으로 받은 마지막 `time`이고(커서가 칸을 떠나면 비운다), 아니면 `timeAt`이 누를 때 묻는다
 *   (이력 비교 — `timeScale().coordinateToTime`). 날짜를 모르면 무시한다 — 직전 날짜로 고르지 않는다
 * - 확대는 **둘째 누름에서만** `timeScale().setVisibleRange`, 리셋은 `fitContent`다. **그릴 때 새 차트 API를 부르지 않는다** — 그 API가
 *   없는 기존 차트 테스트 모의(005~013)가 함께 깨진다(CLAUDE.md 010)
 * - 고르는 동안 Esc는 **고르기만** 취소한다 — `window` 잡기 단계에서 먼저 받아 전파를 멈춘다. 투자 비교 모달(`document`에서 Esc를 받는다)
 *   안의 성과 추이에서 첫 Esc가 모달까지 닫으면 고르기를 무르려다 결과 화면을 잃는다. 고르는 중이 아니면 Esc는 지금처럼 모달을 닫는다
 * - 차트를 다시 만들면(시계열·대상·테마) 차트 효과의 정리에서 `detach`를 불러 처음 범위·단추 없음으로 돌아간다
 * - 화면만이다 — 요청을 보내지 않는다
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { IDLE, cancelPick, isDrag, pickPoint, type ZoomState } from "@/lib/chartZoom";

/** 확대에 쓰는 차트 API — 모두 누를 때만 부른다. */
export interface ZoomableChart {
  timeScale(): {
    fitContent(): void;
    setVisibleRange(range: { from: string; to: string }): void;
    coordinateToTime(x: number): unknown;
  };
}

/** 누를 때 날짜를 묻는다 — `surface`는 누른 차트 칸이다. 모르면 `null`. */
export type TimeAt = (chart: ZoomableChart, clientX: number, surface: HTMLElement) => string | null;

export function useChartZoom(timeAt?: TimeAt) {
  const chart = useRef<ZoomableChart | null>(null);
  const tracked = useRef<string | null>(null);
  const down = useRef<{ x: number; y: number } | null>(null);
  const current = useRef<ZoomState>(IDLE);
  const [state, setState] = useState<ZoomState>(IDLE);

  const commit = useCallback((next: ZoomState) => {
    current.current = next;
    setState(next);
  }, []);

  const attach = useCallback((instance: ZoomableChart) => {
    chart.current = instance;
  }, []);

  const detach = useCallback(() => {
    chart.current = null;
    tracked.current = null;
    down.current = null;
    commit(IDLE);
  }, [commit]);

  const track = useCallback((time: string | undefined) => {
    tracked.current = time ?? null;
  }, []);

  const onMouseDownCapture = useCallback((event: MouseEvent<HTMLElement>) => {
    down.current = { x: event.clientX, y: event.clientY };
  }, []);

  const onClickCapture = useCallback((event: MouseEvent<HTMLElement>) => {
    const pressed = down.current;
    down.current = null;
    if (pressed !== null && isDrag(pressed, { x: event.clientX, y: event.clientY })) return;
    const instance = chart.current;
    if (instance === null) return;
    const date = timeAt === undefined ? tracked.current : timeAt(instance, event.clientX, event.currentTarget);
    if (date === null) return;
    const previous = current.current;
    const next = pickPoint(previous, date);
    // 둘째 누름(다른 날)에서만 확대한다 — 같은 날의 취소는 그 전 범위가 이미 보이고 있다.
    if (previous.kind === "picking" && next.kind === "zoomed" && date !== previous.start) {
      instance.timeScale().setVisibleRange(next.range);
    }
    commit(next);
  }, [commit, timeAt]);

  const cancel = useCallback(() => commit(cancelPick(current.current)), [commit]);

  const reset = useCallback(() => {
    chart.current?.timeScale().fitContent();
    commit(IDLE);
  }, [commit]);

  // 고르는 동안 Esc는 고르기만 취소한다 — 잡기 단계에서 먼저 받아 모달의 Esc(닫기)까지 가지 않게 한다.
  useEffect(() => {
    if (state.kind !== "picking") return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.stopPropagation();
      commit(cancelPick(current.current));
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, [state.kind, commit]);

  return { state, attach, detach, track, surface: { onMouseDownCapture, onClickCapture }, cancel, reset };
}
