/**
 * 최상위 주소 (014 T029) — FR-001, research R14-14.
 *
 * 앱을 처음 여는 주소(`/`)는 대시보드로 옮긴다. 옛 안내 자리("대시보드는 준비 중입니다")는 없다 — 사이드바만 고치고 최상위
 * 주소를 그대로 두면 처음 열 때 여전히 낡은 안내를 본다(FR-001 실패 양상).
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

const redirect = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ redirect }));

describe("최상위 주소", () => {
  it("/dashboard로 옮긴다", async () => {
    const { default: Home } = await import("@/app/page");
    Home();
    expect(redirect).toHaveBeenCalledWith("/dashboard");
  });

  it("옛 안내 글이 없다", () => {
    const source = readFileSync(resolve(__dirname, "../src/app/page.tsx"), "utf-8");
    expect(source).not.toContain("준비 중입니다");
  });
});
