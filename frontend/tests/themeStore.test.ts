/**
 * 화면 테마 스토어 (014 반복 2026-10-10c T131) — FR-030, data-model §9, research R14-23.
 *
 * - 처음은 밝게. `toggle`은 `<html>`의 `dark` 클래스와 브라우저 저장소(`assetreplay.theme`)를 함께 바꾼다
 * - 처음 값은 깜빡임 방지 스크립트가 단 클래스에서 읽는다(`sync`)
 * - 저장소를 쓸 수 없어도(사생활 모드) 지금 화면은 바뀌고 오류가 없다
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { THEME_KEY, useThemeStore } from "@/stores/themeStore";

const html = () => document.documentElement;

beforeEach(() => {
  localStorage.clear();
  html().classList.remove("dark");
  useThemeStore.setState({ theme: "light" });
});

afterEach(() => {
  vi.restoreAllMocks();
  html().classList.remove("dark");
});

describe("테마", () => {
  it("처음은 밝게다", () => {
    useThemeStore.getState().sync();
    expect(useThemeStore.getState().theme).toBe("light");
    expect(html().classList.contains("dark")).toBe(false);
  });

  it("바꾸면 html 클래스와 저장소를 함께 바꾼다", () => {
    useThemeStore.getState().toggle();
    expect(useThemeStore.getState().theme).toBe("dark");
    expect(html().classList.contains("dark")).toBe(true);
    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    useThemeStore.getState().toggle();
    expect(html().classList.contains("dark")).toBe(false);
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
  });

  it("처음 값은 스크립트가 단 클래스다", () => {
    html().classList.add("dark");
    useThemeStore.getState().sync();
    expect(useThemeStore.getState().theme).toBe("dark");
  });

  it("저장소를 쓸 수 없어도 화면은 바뀌고 오류가 없다", () => {
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("SecurityError"); });
    expect(() => useThemeStore.getState().set("dark")).not.toThrow();
    expect(html().classList.contains("dark")).toBe(true);
    expect(useThemeStore.getState().theme).toBe("dark");
  });
});
