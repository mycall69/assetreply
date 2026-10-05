/**
 * 상단 바 제목 (002 FR-004) — 현재 화면의 이름을 보인다.
 *
 * 2026-10-04(008 T036에서 발견): 제목 표가 `/fx`·`/settings`만 알아서 주식(005)·가상자산(007)·예금(008) 화면이 모두
 * "대시보드"로 보였다. 자산군을 더할 때 사이드바에는 경로를 넣고 제목 표는 잊었다 — 오류가 나지 않아 화면을 보기 전까지
 * 몰랐다. 그래서 **사이드바의 이동 가능한 메뉴마다 제목이 메뉴 이름과 같은지**를 본다. 다음 자산군도 여기서 걸린다.
 */
import { describe, expect, it } from "vitest";
import { MENU } from "@/components/shell/Sidebar";
import { screenTitle } from "@/components/shell/TopBar";

describe("상단 바 제목", () => {
  it.each([
    ["/fx", "외환"],
    ["/fx/collection", "수집 현황"],
    ["/crypto", "가상자산"],
    ["/stocks", "주식"],
    ["/deposit", "예금"],
    ["/realestate", "부동산"],
    ["/settings", "설정"],
    ["/", "대시보드"],
  ])("%s → %s", (path, title) => {
    expect(screenTitle(path)).toBe(title);
  });

  it("사이드바의 이동 가능한 메뉴마다 제목이 메뉴 이름과 같다", () => {
    const linked = MENU.filter((m) => m.href !== undefined);
    expect(linked.map((m) => [m.href, screenTitle(m.href as string)]))
      .toEqual(linked.map((m) => [m.href, m.label]));
  });
});
