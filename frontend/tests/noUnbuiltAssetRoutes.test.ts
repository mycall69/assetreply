/**
 * 미구현 자산군 라우트 부재 검사 (T076).
 *
 * 헌법 원칙 IX: 자산군은 한 번에 하나씩 완결한다. 이번 기능은 FX만 구현하며 다른
 * 자산군의 라우트·API 호출을 만들지 않는다 (research R2-9).
 *
 * FR-005: 준비되지 않은 메뉴를 선택해도 빈 화면이나 오류로 이어지면 안 된다. 가장
 * 확실한 방법은 이동할 경로를 아예 만들지 않는 것이다.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(process.cwd(), "src", "app");

/** 헌법 원칙 IX가 고정한 확장 순서상 아직 오지 않은 자산군 */
const UNBUILT = ["stocks", "crypto", "deposits", "realestate", "compare", "dashboard"];

describe("미구현 자산군", () => {
  it("라우트 디렉토리가 존재하지 않는다", () => {
    const present = UNBUILT.filter((slug) => existsSync(join(APP, slug)));
    expect(present).toEqual([]);
  });

  it("사이드바가 준비되지 않은 항목에 경로를 주지 않는다", () => {
    const src = readFileSync(join(process.cwd(), "src/components/shell/Sidebar.tsx"), "utf-8");
    const hrefs = [...src.matchAll(/href:\s*"([^"]+)"/g)].map((m) => m[1]).sort();
    expect(hrefs).toEqual(["/fx", "/settings"]);
  });

  it("다른 자산군 API를 호출하지 않는다", () => {
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((n) => {
        const full = join(dir, n);
        return statSync(full).isDirectory() ? walk(full) : [full];
      });
    const offenders = walk(join(process.cwd(), "src"))
      .filter((f) => /\/api\/(crypto|stocks|deposits|realestate)/.test(readFileSync(f, "utf-8")));
    expect(offenders).toEqual([]);
  });
});
