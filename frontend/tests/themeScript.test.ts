/**
 * 깜빡임 방지 스크립트 (014 반복 2026-10-10c T131) — FR-030, SC-015, research R14-23.
 *
 * 루트 배치의 `<head>`에서 **그리기 전에** 브라우저 저장소를 읽어 `<html>`에 `dark` 클래스를 단다 — 새로고침에 밝은 화면이 번쩍이지 않는다.
 * 저장값이 `dark`가 아니거나 저장소를 읽을 수 없으면 달지 않는다(밝게 — 오류 없음).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { THEME_SCRIPT } from "@/lib/themeScript";
import { THEME_KEY } from "@/stores/themeStore";

// 스크립트는 글자로 `<head>`에 들어간다 — 테스트도 글자를 그대로 실행한다
const run = () => new Function(THEME_SCRIPT)() as void;

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

afterEach(() => {
  vi.restoreAllMocks();
  document.documentElement.classList.remove("dark");
});

describe("깜빡임 방지 스크립트", () => {
  it("저장값이 dark면 dark 클래스를 단다", () => {
    localStorage.setItem(THEME_KEY, "dark");
    run();
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it.each(["light", "black", ""])("그 밖의 값(%s)이면 달지 않는다", (value) => {
    localStorage.setItem(THEME_KEY, value);
    run();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("저장소를 읽을 수 없으면 달지 않고 오류가 없다", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("SecurityError"); });
    expect(run).not.toThrow();
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("루트 배치가 그리기 전에 넣는다", () => {
    const layout = readFileSync(resolve(__dirname, "../src/app/layout.tsx"), "utf-8");
    expect(layout).toMatch(/THEME_SCRIPT/);
    expect(layout).toMatch(/<head>/);
    expect(layout).toMatch(/suppressHydrationWarning/);
  });
});
