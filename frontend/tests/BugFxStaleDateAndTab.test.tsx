/**
 * 회귀 테스트 — `.specify/bugs/fx-stale-date-and-tab/` (2026-09-27).
 *
 * 두 결함을 고정한다.
 *
 *  R2 — 범위 밖 날짜를 골라도 **선택은 반영**된다. 이전 날짜로 되돌리면 안내는
 *       "범위 밖"이라 말하는데 화면은 다른 날짜를 보여줘, 사용자에게는 클릭이 먹지
 *       않은 것처럼 보인다.
 *  R3 — 활성 통화 탭이 비활성과 **시각적으로 구별**된다. 컨테이너에 배경이 없으면
 *       활성 탭의 흰색이 흰 페이지 배경에 묻힌다.
 */
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CurrencyTabs } from "@/components/fx/CurrencyTabs";
import { useFxWorkspaceStore } from "@/stores/fxWorkspaceStore";

describe("R2 — 범위 밖 날짜 선택 (FR-010)", () => {
  beforeEach(() => {
    useFxWorkspaceStore.setState({
      currency: "USD",
      selectedDate: "2020-10-01",
      notice: null,
      coverage: [{
        currency: "USD",
        coveredFrom: "2020-01-01",
        coveredThrough: "2020-12-31",
        firstAvailableDate: "2020-01-01",
        lastUpdatedAt: "2020-12-31T00:00:00",
      }],
    });
  });

  it("범위 밖이어도 선택 날짜가 바뀐다", async () => {
    await useFxWorkspaceStore.getState().selectDate("2026-09-27");
    expect(useFxWorkspaceStore.getState().selectedDate).toBe("2026-09-27");
  });

  it("범위 밖임을 안내한다", async () => {
    await useFxWorkspaceStore.getState().selectDate("2026-09-27");
    const notice = useFxWorkspaceStore.getState().notice;
    expect(notice).not.toBeNull();
    expect(notice?.kind).toBe("out_of_range");
  });

  it("입력값과 안내가 같은 날짜를 가리킨다", async () => {
    // 이전 날짜를 유지하면 둘이 다른 이야기를 한다.
    await useFxWorkspaceStore.getState().selectDate("2026-09-27");
    const s = useFxWorkspaceStore.getState();
    expect(s.selectedDate).toBe("2026-09-27");
    expect(s.notice).not.toBeNull();
  });

  it("범위 안이면 안내가 없다", async () => {
    await useFxWorkspaceStore.getState().selectDate("2020-06-15");
    expect(useFxWorkspaceStore.getState().selectedDate).toBe("2020-06-15");
    expect(useFxWorkspaceStore.getState().notice).toBeNull();
  });
});

describe("R3 — 활성 통화 탭 식별", () => {
  it("활성 탭이 aria-selected로 드러난다", () => {
    render(<CurrencyTabs value="USD" onChange={vi.fn()} />);
    const usd = screen.getByRole("tab", { name: /USD/ });
    expect(usd.getAttribute("aria-selected")).toBe("true");
  });

  it("활성과 비활성의 클래스가 다르다", () => {
    render(<CurrencyTabs value="USD" onChange={vi.fn()} />);
    const usd = screen.getByRole("tab", { name: /USD/ });
    const jpy = screen.getByRole("tab", { name: /JPY/ });
    expect(usd.className).not.toBe(jpy.className);
  });

  it("활성 탭이 배경색을 갖는다", () => {
    render(<CurrencyTabs value="USD" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: /USD/ }).className).toMatch(/bg-white/);
  });

  it("컨테이너가 활성 탭과 다른 배경을 갖는다", () => {
    // 이것이 없으면 활성 탭의 흰색이 흰 페이지 배경에 묻힌다.
    render(<CurrencyTabs value="USD" onChange={vi.fn()} />);
    const list = screen.getByRole("tablist");
    expect(list.className).toMatch(/bg-gray-\d+/);
  });

  it("비활성 탭은 배경이 없다", () => {
    render(<CurrencyTabs value="USD" onChange={vi.fn()} />);
    expect(screen.getByRole("tab", { name: /JPY/ }).className).not.toMatch(/bg-white/);
  });
});
