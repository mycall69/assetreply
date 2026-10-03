/**
 * 미구현 자산군 라우트 부재 검사 (T076).
 *
 * 헌법 원칙 IX: 자산군은 한 번에 하나씩 완결한다. 아직 오지 않은 자산군의 라우트·API
 * 호출을 만들지 않는다 (002 research R2-9).
 *
 * **이 가드가 이름에 기대고 있다.** 005에서 라우트를 `stock`(단수)로 두려다 이 목록과
 * 어긋나 가드가 실패가 아니라 **통과**할 뻔했다 — false pass는 실패보다 나쁘다.
 *
 * FR-005: 준비되지 않은 메뉴를 선택해도 빈 화면이나 오류로 이어지면 안 된다. 가장
 * 확실한 방법은 이동할 경로를 아예 만들지 않는 것이다.
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const APP = join(process.cwd(), "src", "app");

/**
 * 아직 오지 않은 자산군.
 *
 * **2026-10-02: `stocks`를 뺐다.** 005가 주식 시뮬레이션을 구현해 더 이상 "준비되지
 * 않은" 상태가 아니다. 자산군 순서(원칙 IX)에서 가상자산을 건너뛴 이탈은 005 plan의
 * Complexity Tracking에 기록돼 있으며, 가상자산은 006으로 수행한다.
 */
const UNBUILT = ["crypto", "deposits", "realestate", "compare", "dashboard"];

describe("미구현 자산군", () => {
  it("라우트 디렉토리가 존재하지 않는다", () => {
    const present = UNBUILT.filter((slug) => existsSync(join(APP, slug)));
    expect(present).toEqual([]);
  });

  it("사이드바가 준비되지 않은 항목에 경로를 주지 않는다", () => {
    const src = readFileSync(join(process.cwd(), "src/components/shell/Sidebar.tsx"), "utf-8");
    const hrefs = [...src.matchAll(/href:\s*"([^"]+)"/g)].map((m) => m[1]).sort();
    expect(hrefs).toEqual(["/fx", "/settings", "/stocks"]);
  });

  /**
   * **2026-10-03: API 호출 검사에서 `crypto`를 뺐다**(007 T028을 T020으로 앞당김). 007의 코인 검색 칸(T020)이
   * `/api/crypto/search`를 부른다. 라우트 디렉토리·사이드바 검사의 `crypto`는 화면을 만드는 T028·T033에서 뺀다.
   */
  it("다른 자산군 API를 호출하지 않는다", () => {
    const walk = (dir: string): string[] =>
      readdirSync(dir).flatMap((n) => {
        const full = join(dir, n);
        return statSync(full).isDirectory() ? walk(full) : [full];
      });
    const offenders = walk(join(process.cwd(), "src"))
      .filter((f) => /\/api\/(deposits|realestate)/.test(readFileSync(f, "utf-8")));
    expect(offenders).toEqual([]);
  });
});
