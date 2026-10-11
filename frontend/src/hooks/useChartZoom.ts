"use client";

/**
 * 수익률 그래프의 두 지점 확대 (014 반복 2026-10-11b) — spec FR-037, data-model 15, research R14-30, contracts D16.
 *
 * - 누름은 **차트 칸의 DOM 이벤트**다(잡기 단계 — 라이브러리가 캔버스에서 전파를 막아도 받는다). 눌렀다 뗀 사이 4px 넘게 움직였으면
 *   끌기(라이브러리의 옮기기)라 세지 않는다
 * - 누른 날짜는 커서를 쫓는 그래프면 `track`으로 받은 마지막 `time`이고(커서가 칸을 떠나면 비운다), 아니면 `timeAt`이 누를 때 묻는다
 *   (이력 비교 — `timeScale().coordinateToTime`). 날짜를 모르면 무시한다 — 직전 날짜로 고르지 않는다
 * - 확대는 **둘째 누름에서만** `timeScale().setVisibleRange`, 리셋은 `fitContent`다(`resetView`가 있으면 그것 — 지표 그래프는 기간의 처음 범위).
 *   **그릴 때 새 차트 API를 부르지 않는다** — 그 API가 없는 기존 차트 테스트 모의(005~013)가 함께 깨진다(CLAUDE.md 010)
 * - 고르는 동안 Esc는 **고르기만** 취소한다 — `window` 잡기 단계에서 먼저 받아 전파를 멈춘다. 투자 비교 모달(`document`에서 Esc를 받는다)
 *   안의 성과 추이에서 첫 Esc가 모달까지 닫으면 고르기를 무르려다 결과 화면을 잃는다. 고르는 중이 아니면 Esc는 지금처럼 모달을 닫는다
 * - 차트를 다시 만들면(시계열·대상·테마) 차트 효과의 정리에서 `detach`를 불러 처음 범위·단추 없음으로 돌아간다. 받은 일 단위 자료로만
 *   다시 그릴 때는 `release`(차트만 놓는다 — 확대 상태 그대로)를 부르고, 바탕 자료가 바뀌면 `clear`로 상태를 비운다(014 반복 2026-10-11c)
 * - (014 반복 2026-10-11c — FR-038·FR-039) 확대가 끝나면 `onZoom(범위)`을 알린다 — 그래프가 그 구간의 일 단위 자료를 받는다. 리셋하면
 *   `onReset`이다. 확대 단추 자리는 오른쪽 가격 축 밖이다 — 처음 누를 때 축 폭(`priceScale("right").width()`)을 잰다(누를 때만 부른다)
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { MouseEvent } from "react";
import { IDLE, cancelPick, isDrag, pickPoint, type ZoomRange, type ZoomState } from "@/lib/chartZoom";

/** 확대에 쓰는 차트 API — 모두 누를 때만 부른다. */
export interface ZoomableChart {
  timeScale(): {
    fitContent(): void;
    setVisibleRange(range: { from: string; to: string }): void;
    coordinateToTime(x: number): unknown;
  };
  priceScale(id: string): { width(): number };
}

/** 누를 때 날짜를 묻는다 — `surface`는 누른 차트 칸이다. 모르면 `null`. */
export type TimeAt = (chart: ZoomableChart, clientX: number, surface: HTMLElement) => string | null;

export interface ChartZoomOptions {
  timeAt?: TimeAt;
  /** 확대가 끝났다(새 범위). 같은 날의 취소·받은 구간 안의 재확대도 범위가 바뀌면 알린다. */
  onZoom?: (range: ZoomRange) => void;
  /** [리셋]을 눌렀다 — 받은 자료를 버린다. */
  onReset?: () => void;
  /** 처음 범위로 되돌리는 방법 — 없으면 `fitContent`. */
  resetView?: (chart: ZoomableChart) => void;
}

/** 확대 단추·상태 줄과 오른쪽 가격 축 사이의 틈(px). */
export const ZOOM_CONTROLS_GAP = 8;

export function useChartZoom(options: ChartZoomOptions = {}) {
  const chart = useRef<ZoomableChart | null>(null);
  const tracked = useRef<string | null>(null);
  const down = useRef<{ x: number; y: number } | null>(null);
  const current = useRef<ZoomState>(IDLE);
  const latest = useRef(options);
  const [state, setState] = useState<ZoomState>(IDLE);
  const [axisWidth, setAxisWidth] = useState(0);

  // 알림 함수는 그릴 때마다 새로 온다 — 누를 때의 것을 쓴다.
  useEffect(() => {
    latest.current = options;
  });

  const commit = useCallback((next: ZoomState) => {
    current.current = next;
    setState(next);
  }, []);

  const attach = useCallback((instance: ZoomableChart) => {
    chart.current = instance;
  }, []);

  /** 차트만 놓는다 — 확대 상태는 그대로(받은 자료로 다시 그릴 때). */
  const release = useCallback(() => {
    chart.current = null;
    tracked.current = null;
    down.current = null;
  }, []);

  /** 확대 상태만 비운다 — 바탕 자료·테마가 바뀌었다. */
  const clear = useCallback(() => commit(IDLE), [commit]);

  const detach = useCallback(() => {
    release();
    commit(IDLE);
  }, [release, commit]);

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
    const { timeAt } = latest.current;
    const date = timeAt === undefined ? tracked.current : timeAt(instance, event.clientX, event.currentTarget);
    if (date === null) return;
    const previous = current.current;
    const next = pickPoint(previous, date);
    // 단추 자리 — 오른쪽 가격 축 밖. 처음 고르기를 시작할 때 잰다(축 폭은 확대 중에 바뀌지 않는다).
    if (previous.kind === "idle") setAxisWidth(instance.priceScale("right").width());
    // 둘째 누름(다른 날)에서만 확대한다 — 같은 날의 취소는 그 전 범위가 이미 보이고 있다.
    const zoomed = previous.kind === "picking" && next.kind === "zoomed" && date !== previous.start;
    if (zoomed) instance.timeScale().setVisibleRange(next.range);
    commit(next);
    if (zoomed) latest.current.onZoom?.(next.range);
  }, [commit]);

  const cancel = useCallback(() => commit(cancelPick(current.current)), [commit]);

  const reset = useCallback(() => {
    const instance = chart.current;
    if (instance !== null) {
      const { resetView } = latest.current;
      if (resetView === undefined) instance.timeScale().fitContent();
      else resetView(instance);
    }
    commit(IDLE);
    latest.current.onReset?.();
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

  return {
    state, attach, detach, release, clear, track, surface: { onMouseDownCapture, onClickCapture }, cancel, reset,
    /** 확대 단추·상태 줄의 자리 — 그래프 칸 오른쪽 끝에서 이만큼(px). */
    controlsRight: axisWidth + ZOOM_CONTROLS_GAP,
  };
}
