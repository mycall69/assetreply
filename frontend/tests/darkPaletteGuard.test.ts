/**
 * 블랙 팔레트 가드 (014 반복 2026-10-10c T131) — FR-030 실패 양상, SC-015, research R14-23.
 *
 * 블랙 테마는 컴포넌트 클래스를 바꾸지 않고 Tailwind 색 변수를 `.dark` 아래에서 다시 정의한다. src가 쓰는 색 유틸리티 가운데 하나라도
 * 재정의가 빠지면 그 부품만 밝은 색으로 남아 글자가 배경에 묻힌다(전에 OS 다크 모드에서 사이드바 글자가 묻혔다 — `globals.css`의 옛 주석).
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = resolve(__dirname, "../src");
const UTILITY = /\b(?:bg|text|border|ring|divide|from|to|via|fill|stroke|outline|decoration|placeholder|accent|caret)(?:-[trblxy])?-(white|black|(?:slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-\d{2,3})\b/g;

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(tsx?|css)$/.test(name) && !name.endsWith("globals.css") ? [path] : [];
  });
}

function darkBlock(): string {
  const css = readFileSync(join(SRC, "app/globals.css"), "utf-8");
  const start = css.search(/(^|\n)\s*(html)?\.dark\s*\{/);
  expect(start).toBeGreaterThanOrEqual(0);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  return css.slice(open, close);
}

describe("블랙 팔레트", () => {
  const used = new Set<string>();
  for (const file of files(SRC)) {
    for (const match of readFileSync(file, "utf-8").matchAll(UTILITY)) used.add(match[1]);
  }

  it("검사할 색이 있다", () => {
    expect(used.size).toBeGreaterThan(10);
    expect(used.has("gray-500")).toBe(true);
  });

  it.each([...used].sort())("--color-%s를 .dark에서 다시 정의한다", (color) => {
    expect(darkBlock()).toContain(`--color-${color}:`);
  });

  it("본문 바탕·글자 변수도 다시 정의한다", () => {
    const block = darkBlock();
    expect(block).toContain("--background:");
    expect(block).toContain("--foreground:");
    expect(block).toContain("color-scheme: dark");
  });
});
