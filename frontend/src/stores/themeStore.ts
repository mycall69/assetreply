/**
 * 화면 테마 스토어 (014 반복 2026-10-10c T135) — FR-030, data-model §7·§9, research R14-23.
 *
 * - 테마는 `<html>`의 `dark` 클래스다. 색은 `globals.css`의 `.dark` 변수 재정의가 바꾼다 — 컴포넌트 클래스는 그대로다
 * - 처음 값은 깜빡임 방지 스크립트(`lib/themeScript`)가 그리기 전에 단 클래스다(`sync`). 서버·DB에 두지 않는다 — 화면 설정이다
 * - 바꾸면 클래스와 브라우저 저장소를 함께 바꾼다. 저장소를 쓸 수 없어도(사생활 모드) 지금 화면은 바뀐다 — 그 탭에서만 유지된다
 */
import { create } from "zustand";
import { THEME_KEY } from "@/lib/themeScript";

export { THEME_KEY };

export type Theme = "light" | "dark";

function documentTheme(): Theme {
  return typeof document !== "undefined" && document.documentElement.classList.contains("dark") ? "dark" : "light";
}

interface ThemeState {
  theme: Theme;
  set: (theme: Theme) => void;
  toggle: () => void;
  /** `<html>`의 클래스(스크립트가 단 처음 값)를 읽는다. */
  sync: () => void;
}

export const useThemeStore = create<ThemeState>((setState, get) => ({
  theme: documentTheme(),

  set: (theme) => {
    if (typeof document !== "undefined") document.documentElement.classList.toggle("dark", theme === "dark");
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      // 저장소를 쓸 수 없다(사생활 모드 등) — 지금 화면만 바꾼다
    }
    setState({ theme });
  },

  toggle: () => get().set(get().theme === "dark" ? "light" : "dark"),

  sync: () => setState({ theme: documentTheme() }),
}));
