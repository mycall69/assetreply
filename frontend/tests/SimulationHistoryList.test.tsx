/**
 * 이력 목록 테스트 (T086) — 005 FR-035~037b, SC-014, SC-018, ui-wireframes W5.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { SimulationHistory } from "@/components/stock/SimulationHistory";
import type { SimulationHistoryEntry } from "@/lib/types";

const ENTRIES: SimulationHistoryEntry[] = [
  {
    id: "a", savedAt: "2026-10-01T09:00:00.000Z",
    stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
    start: "2021-08-01", principal: "86997", principalCurrency: "KRW",
    reinvest: true,
  },
  {
    id: "b", savedAt: "2026-10-01T08:00:00.000Z",
    stock: { market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" },
    start: "2021-08-01", principal: "86997", principalCurrency: "KRW",
    reinvest: false,
  },
];

const base = {
  entries: ENTRIES,
  selected: [] as string[],
  comparing: false,
  saveError: null,
  onToggle: vi.fn(),
  onRemove: vi.fn(),
  onCompare: vi.fn(),
};

describe("최근 시뮬레이션", () => {
  it("이 브라우저에만 저장된다는 사실을 알린다", () => {
    // FR-037a, SC-018 — 알리지 않으면 사용자는 계정에 딸린 기록으로 여겨,
    // 다른 기기에서 열었을 때 사라진 것으로 오해한다.
    render(<SimulationHistory {...base} />);
    expect(screen.getByTestId("history-notice").textContent).toMatch(
      /이 브라우저/,
    );
  });

  it("브라우저 데이터를 지우면 함께 사라진다는 점도 알린다", () => {
    render(<SimulationHistory {...base} />);
    expect(screen.getByTestId("history-notice").textContent).toMatch(/지우면/);
  });

  it("항목마다 종목·시작일·원금·재투자 여부를 보인다", () => {
    // FR-036, SC-014 — 두 항목은 재투자 여부만 다르다. 그것이 안 보이면 같은 줄이다.
    render(<SimulationHistory {...base} />);
    const rows = screen.getAllByTestId("history-row");
    expect(rows[0].textContent).toContain("삼성전자");
    expect(rows[0].textContent).toContain("2021-08-01");
    expect(rows[0].textContent).toContain("86,997");
    expect(rows[0].textContent).toContain("재투자 O");
    expect(rows[1].textContent).toContain("재투자 X");
  });

  it("항목을 지울 수 있다", () => {
    // FR-037b
    const onRemove = vi.fn();
    render(<SimulationHistory {...base} onRemove={onRemove} />);
    fireEvent.click(screen.getAllByRole("button", { name: /삭제/ })[0]);
    expect(onRemove).toHaveBeenCalledWith("a");
  });

  it("둘 이상 골라야 비교할 수 있다", () => {
    // FR-038 — 하나만 고른 비교는 비교가 아니다. 눌리면 사용자는 기다리게 된다.
    const { rerender } = render(<SimulationHistory {...base} selected={["a"]} />);
    expect(screen.getByRole("button", { name: /비교/ })).toBeDisabled();
    rerender(<SimulationHistory {...base} selected={["a", "b"]} />);
    expect(screen.getByRole("button", { name: /비교/ })).toBeEnabled();
  });

  it("고른 항목으로 비교를 실행한다", () => {
    const onCompare = vi.fn();
    render(
      <SimulationHistory {...base} selected={["a", "b"]} onCompare={onCompare} />,
    );
    fireEvent.click(screen.getByRole("button", { name: /비교/ }));
    expect(onCompare).toHaveBeenCalled();
  });

  it("저장에 실패했으면 그 사실을 알린다", () => {
    // R5-10 — 조용히 실패하면 사용자는 저장된 줄 알고 다음에 열었을 때 비어 있다.
    render(<SimulationHistory {...base} saveError="이력을 저장하지 못했습니다." />);
    expect(screen.getByRole("alert").textContent).toContain("저장하지 못했습니다");
  });

  it("이력이 없으면 빈 상태를 알린다", () => {
    render(<SimulationHistory {...base} entries={[]} />);
    expect(screen.getByText(/아직 실행한 시뮬레이션이 없습니다/)).toBeInTheDocument();
    // 비어 있어도 보관 위치 안내는 남는다 — 그때가 오해가 생기는 시점이다.
    expect(screen.getByTestId("history-notice")).toBeInTheDocument();
  });
});
