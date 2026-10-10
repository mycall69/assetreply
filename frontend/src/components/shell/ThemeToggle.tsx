"use client";

/**
 * 테마 단추 — 블랙 배경 (014 반복 2026-10-10c T135) — FR-030, US4, contracts D6·D9.
 *
 * 상단 바 오른쪽 끝에 늘 있다. `role="switch"`·이름 "블랙 배경"·`aria-checked` — 기호(☾·☀)만으로 뜻을 전하지 않는다.
 * 서버는 늘 밝은 화면을 그린다(저장값을 모른다) — 붙을 때는 서버 값으로 맞추고(`getServerSnapshot`), 곧바로 스크립트가 단 실제 테마로 다시 그린다.
 * 그러지 않으면 `aria-checked`가 서버 값으로 남는다.
 */
import { useEffect, useSyncExternalStore } from "react";
import { useThemeStore, type Theme } from "@/stores/themeStore";

const light = (): Theme => "light";

export function ThemeToggle() {
  const theme = useSyncExternalStore(useThemeStore.subscribe, () => useThemeStore.getState().theme, light);
  useEffect(() => useThemeStore.getState().sync(), []);
  const dark = theme === "dark";
  return (
    <button type="button" role="switch" aria-checked={dark} aria-label="블랙 배경" title="블랙 배경"
      onClick={() => useThemeStore.getState().toggle()}
      className="rounded px-2 py-1 text-base leading-none text-gray-600 hover:bg-gray-100 hover:text-gray-900">
      <span aria-hidden="true">{dark ? "☀" : "☾"}</span>
    </button>
  );
}
