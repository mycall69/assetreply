/**
 * 차트 다섯 종의 테마 (014 반복 2026-10-10c T136) — FR-030, SC-015, research R14-23.
 *
 * Lightweight Charts는 CSS 변수를 읽지 않는다 — 화면이 블랙이어도 차트는 라이브러리 기본(흰 바탕·검은 글자)으로 남아 흰 상자가 된다
 * (FR-030 실패 양상). 그래서 차트를 만들 때 테마의 팔레트를 넘기고, 테마가 바뀌면 **다시 만든다** — `applyOptions`는 005~013 차트 테스트의
 * 인라인 모의에 없어 실행 중에 쓰면 그 테스트가 깨진다(CLAUDE.md 010 주의).
 *
 * **밝은 테마는 받은 선택 그대로다** — 배경·격자를 넣지 않는다. 이 반복 전과 같은 값이라 밝은 화면이 바뀌지 않는다(FR-026).
 */
import type { Theme } from "@/stores/themeStore";

/** 블랙 테마의 차트 색 — `globals.css`의 `.dark` 팔레트와 맞춘다(바탕 `--color-white`, 글자 `--color-gray-700`, 격자 `--color-gray-100`). */
export const DARK_CHART = {
  background: "#0b0f14",
  text: "#cfd4dc",
  grid: "#1a2130",
} as const;

/** 밝은 바탕용 선 색 → 블랙 바탕에서 보이는 색. 목록 밖 색(파랑·주황 등)은 두 바탕에서 다 보여 그대로다. */
const DARK_INK: Record<string, string> = {
  "#1f2937": "#e2e5ea",
  "#9ca3af": "#7b8494",
  "#ffffff": DARK_CHART.background,
};

/** 차트 만들기 선택에 테마를 더한다. 밝으면 그대로. */
export function themedChartOptions<T extends object>(options: T, theme: Theme): T {
  if (theme === "light") return options;
  const layout = (options as { layout?: object }).layout ?? {};
  return {
    ...options,
    layout: { ...layout, background: { color: DARK_CHART.background }, textColor: DARK_CHART.text },
    grid: { vertLines: { color: DARK_CHART.grid }, horzLines: { color: DARK_CHART.grid } },
  };
}

/** 선·점 색. 밝으면 그대로, 블랙이면 밝은 바탕용 진한 회색·흰색을 블랙 바탕에서 보이는 색으로. */
export function ink(color: string, theme: Theme): string {
  return theme === "light" ? color : DARK_INK[color.toLowerCase()] ?? color;
}
