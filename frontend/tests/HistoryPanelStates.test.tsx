/**
 * 이력 칸의 안내와 상태 (012 T048) — FR-014, FR-014a, FR-015, contracts/ui-wireframes.md F6.
 *
 * - 안내는 보관 위치(이 기기의 로컬 DB)와 보관 기간을 말한다. "이 브라우저에만 저장됩니다"를 대체한다. 자산군 구별 문구는 지금 그대로다
 * - 불러오는 중에는 빈 상태 문구("아직 실행한 시뮬레이션이 없습니다")를 보이지 않는다 — 비어 있는 것으로 오해한다
 * - 불러오기 실패는 `role="alert"`와 다시 시도 단추다. 빈 상태 문구를 보이지 않는다(FR-014a — 실패가 빈 목록으로 보이면 지워졌다고 오해한다)
 * - 옮기지 못한 항목 수를 알린다. 새 속성은 모두 선택이다 — 지금 속성만으로 그려도 그대로다
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ComponentType } from "react";
import { describe, expect, it, vi } from "vitest";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { DepositHistory } from "@/components/deposit/DepositHistory";
import { RealEstateHistory } from "@/components/realestate/RealEstateHistory";
import { SimulationHistory } from "@/components/stock/SimulationHistory";

const common = {
  entries: [], selected: [], comparing: false, saveError: null,
  onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn(),
};

interface StateProps {
  loading?: boolean;
  loadError?: string | null;
  onRetry?: () => void;
  notice?: string | null;
  retentionDays?: number | null;
}

const PANELS: Array<{ name: string; Panel: ComponentType<typeof common & StateProps>; scope: string }> = [
  { name: "주식", Panel: SimulationHistory as unknown as ComponentType<typeof common & StateProps>, scope: "" },
  { name: "가상자산", Panel: CryptoHistory as unknown as ComponentType<typeof common & StateProps>, scope: " 주식 이력과 따로입니다." },
  { name: "예금", Panel: DepositHistory as unknown as ComponentType<typeof common & StateProps>,
    scope: " 주식·가상자산 이력과 따로입니다." },
  { name: "부동산", Panel: RealEstateHistory as unknown as ComponentType<typeof common & StateProps>,
    scope: " 다른 자산군 이력과 따로입니다." },
];

describe.each(PANELS)("$name 이력 칸", ({ Panel, scope }) => {
  it("보관 위치와 기간을 말하고 '이 브라우저'가 없다", () => {
    render(<Panel {...common} retentionDays={30} />);
    expect(screen.getByTestId("history-notice")).toHaveTextContent(
      `ⓘ 이 기기의 로컬 DB에 저장됩니다. 마지막 실행 뒤 30일이 지나면 지워집니다 — 기간은 설정에서 바꿉니다.${scope}`);
    expect(screen.queryByText(/이 브라우저/)).toBeNull();
  });

  it("무기한이면 기한 없이 남는다고 말한다", () => {
    render(<Panel {...common} retentionDays={null} />);
    expect(screen.getByTestId("history-notice")).toHaveTextContent(
      "ⓘ 이 기기의 로컬 DB에 저장됩니다. 기한 없이 남습니다 — 기간은 설정에서 바꿉니다.");
  });

  it("불러오는 중에는 빈 상태 문구가 없다", () => {
    render(<Panel {...common} loading />);
    expect(screen.getByText("⟳ 불러오는 중…")).toBeInTheDocument();
    expect(screen.queryByText("아직 실행한 시뮬레이션이 없습니다.")).toBeNull();
  });

  it("불러오기 실패는 알림과 다시 시도 단추이고 빈 상태 문구가 없다", async () => {
    const onRetry = vi.fn();
    render(<Panel {...common} loadError="이력을 불러오지 못했습니다." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("이력을 불러오지 못했습니다.");
    expect(screen.queryByText("아직 실행한 시뮬레이션이 없습니다.")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("옮기지 못한 항목 수를 알린다", () => {
    render(<Panel {...common} notice="읽을 수 없는 브라우저 이력 1개는 옮기지 못했습니다." />);
    expect(screen.getByRole("status")).toHaveTextContent("읽을 수 없는 브라우저 이력 1개는 옮기지 못했습니다.");
  });

  it("지금 속성만으로 그려도 빈 상태 문구가 보인다", () => {
    render(<Panel {...common} />);
    expect(screen.getByText("아직 실행한 시뮬레이션이 없습니다.")).toBeInTheDocument();
    expect(screen.getByTestId("history-notice")).toHaveTextContent("ⓘ 이 기기의 로컬 DB에 저장됩니다.");
  });
});
