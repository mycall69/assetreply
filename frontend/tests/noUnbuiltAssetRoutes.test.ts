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
 * **2026-10-05: `realestate`를 뺐다.** 009가 부동산 시뮬레이션을 구현했다(T026). 경로는 `realestate`(`/realestate`,
 * `/api/realestate/*`)로 이 목록의 이름과 같다 — 지우지 않으면 라우트 디렉토리 검사가 실패한다. 사이드바 경로 검사에도
 * `/realestate`를 더했다. 이제 남은 것은 자산군이 아닌 두 화면(투자 비교·대시보드)이다.
 *
 * **2026-10-04: `deposits`를 뺐다.** 008이 예금 시뮬레이션을 구현했다(T021). 경로는 단수 `deposit`(`/deposit`,
 * `/api/deposit/*`)이다 — 이 목록의 복수 이름과 달라 지우지 않아도 가드가 통과한다. 그래서 목록에서 지우고 사이드바 경로
 * 검사에 `/deposit`을 더해 이름이 어긋나도 드러나게 했다.
 *
 * **2026-10-03: `crypto`를 뺐다.** 007이 가상자산 시뮬레이션을 구현했다(T028·T033).
 *
 * **2026-10-02: `stocks`를 뺐다.** 005가 주식 시뮬레이션을 구현해 더 이상 "준비되지
 * 않은" 상태가 아니다. 자산군 순서(원칙 IX)에서 가상자산을 건너뛴 이탈은 005 plan의
 * Complexity Tracking에 기록돼 있으며, 가상자산은 006으로 수행한다.
 */
// 013 승인 2026-10-08 — 013이 투자 비교 화면(`src/app/compare`)을 만들어 `compare`를 뺐다.
const UNBUILT = ["dashboard"];

describe("미구현 자산군", () => {
  it("라우트 디렉토리가 존재하지 않는다", () => {
    const present = UNBUILT.filter((slug) => existsSync(join(APP, slug)));
    expect(present).toEqual([]);
  });

  it("사이드바가 준비되지 않은 항목에 경로를 주지 않는다", () => {
    const src = readFileSync(join(process.cwd(), "src/components/shell/Sidebar.tsx"), "utf-8");
    const hrefs = [...src.matchAll(/href:\s*"([^"]+)"/g)].map((m) => m[1]).sort();
    // 013 승인 2026-10-08 — 사이드바에 투자 비교(`/compare`)가 더해졌다.
    expect(hrefs).toEqual(["/compare", "/crypto", "/deposit", "/fx", "/realestate", "/settings", "/stocks"]);
  });

  /**
   * **2026-10-05: API 호출 검사에서 `realestate`를 빼고 남은 두 화면(`compare`·`dashboard`)을 넣었다** — 009가
   * `/api/realestate/*`를 부른다. 검사 대상이 비면 가드가 아무것도 막지 않은 채 늘 통과한다.
   *
   * **2026-10-04: API 호출 검사에서 `deposits`를 뺐다** — 008이 `/api/deposit/*`를 부른다.
   *
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
      .filter((f) => /\/api\/(compare|dashboard)\b/.test(readFileSync(f, "utf-8")));
    expect(offenders).toEqual([]);
  });
});
