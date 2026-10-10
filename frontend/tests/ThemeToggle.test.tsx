/**
 * 상단 바의 테마 단추 (014 반복 2026-10-10c T131) — FR-030, US4, contracts D6·D9.
 *
 * - 모든 화면의 상단 바 오른쪽 끝(수집 표시기 오른쪽)에 있다. 상단 바는 스크롤해도 위에 붙어 있다(`sticky top-0`)
 * - `role="switch"`·이름 "블랙 배경"·`aria-checked`. 키보드(Space·Enter)로 누른다
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TopBar } from "@/components/shell/TopBar";
import { useThemeStore } from "@/stores/themeStore";

vi.mock("next/navigation", () => ({ usePathname: () => "/stocks" }));
vi.mock("@/components/shell/CollectionIndicator", () => ({ CollectionIndicator: () => <span data-testid="collection" /> }));

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  useThemeStore.setState({ theme: "light" });
});

afterEach(() => document.documentElement.classList.remove("dark"));

describe("테마 단추", () => {
  it("상단 바 오른쪽 끝에 있고 상단 바는 위에 붙는다", () => {
    render(<TopBar />);
    const toggle = screen.getByRole("switch", { name: "블랙 배경" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    const header = screen.getByRole("banner");
    expect(header.className).toMatch(/\bsticky\b/);
    expect(header.className).toMatch(/\btop-0\b/);
    // 수집 표시기 다음 — 오른쪽 끝
    const collection = screen.getByTestId("collection");
    expect(collection.compareDocumentPosition(toggle) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("누르면 블랙이고 다시 누르면 밝게다", async () => {
    const user = userEvent.setup();
    render(<TopBar />);
    const toggle = screen.getByRole("switch", { name: "블랙 배경" });
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    await user.click(toggle);
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("키보드로 누른다", async () => {
    const user = userEvent.setup();
    render(<TopBar />);
    await user.tab();
    expect(screen.getByRole("switch", { name: "블랙 배경" })).toHaveFocus();
    await user.keyboard("[Space]");
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    await user.keyboard("[Enter]");
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });
});
