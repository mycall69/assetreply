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

/** `.dark` 블록의 `--color-…: #rrggbb` 값. */
function darkValues(): Record<string, string> {
  const out: Record<string, string> = {};
  for (const m of darkBlock().matchAll(/--color-([a-z]+(?:-\d{2,3})?):\s*(#[0-9a-fA-F]{6})/g)) out[m[1]] = m[2];
  return out;
}

function luminance(hex: string): number {
  const channel = (i: number) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("블랙 팔레트 대비(SC-015)", () => {
  // T137 실측(2026-10-10) — 외환 통화 탭(`bg-gray-100`) 안의 `text-gray-400` 보조 글자가 4.27:1이었다
  const values = darkValues();
  const surfaces = ["white", "gray-50", "gray-100"];
  const texts = ["gray-400", "gray-500", "gray-600", "gray-700", "gray-800", "gray-900", "red-700", "blue-700", "emerald-700"];

  it.each(texts.flatMap((t) => surfaces.map((s) => [t, s] as const)))("%s 글자는 %s 바탕에서 4.5:1 이상이다", (text, surface) => {
    expect(contrast(values[text], values[surface])).toBeGreaterThanOrEqual(4.5);
  });

  it.each([["amber-800", "amber-50"], ["amber-900", "amber-50"], ["red-700", "red-50"], ["sky-800", "sky-50"], ["green-800", "green-100"]] as const)(
    "%s 글자는 %s 경고·알림 바탕에서 4.5:1 이상이다", (text, surface) => {
      expect(contrast(values[text], values[surface])).toBeGreaterThanOrEqual(4.5);
    });
});
