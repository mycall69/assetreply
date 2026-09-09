/**
 * 수집 현황의 잠정 잔존 경고 (T089) — FR-043a.
 *
 * 잠정 잔존은 확정 전환이 일어나지 않았다는 뜻이다. 경고만 띄우고 **무엇을 하면
 * 해소되는지** 알려주지 않으면 운영자가 할 수 있는 일이 없다.
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CollectionStatus } from "@/components/CollectionStatus";
import type { CoverageRow } from "@/lib/types";

const BASE: CoverageRow = {
  currency: "USD", coveredFrom: "1964-01-01", coveredThrough: "2026-09-08",
  firstAvailableDate: "1964-05-04", lastUpdatedAt: "2026-09-09T01:12:00Z",
};

const props = { jobs: [], loading: false, onCollect: vi.fn() };

describe("잠정 잔존 경고", () => {
  it("잔존이 없으면 경고를 띄우지 않는다", () => {
    render(<CollectionStatus {...props} coverage={[BASE]} />);
    expect(screen.queryByText(/확정되지 않았습니다/)).toBeNull();
  });

  it("잔존이 있으면 해당 통화 행에 날짜와 함께 표시한다", () => {
    render(
      <CollectionStatus {...props}
        coverage={[{ ...BASE, staleProvisional: { date: "2026-09-05" } }]} />,
    );
    const warning = screen.getByTestId("stale-USD");
    expect(warning.textContent).toContain("2026-09-05");
    expect(warning.textContent).toContain("확정되지 않았습니다");
  });

  it("해소 방법을 함께 알린다", () => {
    render(
      <CollectionStatus {...props}
        coverage={[{ ...BASE, staleProvisional: { date: "2026-09-05" } }]} />,
    );
    expect(screen.getByTestId("stale-USD").textContent).toMatch(/수집을 실행/);
  });

  it("잔존이 있는 통화만 표시한다", () => {
    render(
      <CollectionStatus {...props}
        coverage={[
          { ...BASE, staleProvisional: { date: "2026-09-05" } },
          { ...BASE, currency: "JPY" },
        ]} />,
    );
    expect(screen.getByTestId("stale-USD")).toBeInTheDocument();
    expect(screen.queryByTestId("stale-JPY")).toBeNull();
  });

  it("경고를 색이 아닌 문구로도 전달한다", () => {
    /** 색만으로 알리면 색각 이상 사용자가 읽을 수 없다. 기호와 문장을 함께 쓴다. */
    render(
      <CollectionStatus {...props}
        coverage={[{ ...BASE, staleProvisional: { date: "2026-09-05" } }]} />,
    );
    const row = screen.getByText("USD").closest("tr") as HTMLElement;
    // 통화 열의 기호와 안내 문구가 둘 다 있어야 한다
    expect(within(row).getAllByText(/⚠/).length).toBeGreaterThanOrEqual(2);
    expect(within(row).getByTestId("stale-USD").textContent).toMatch(/확정되지 않았습니다/);
  });
});
