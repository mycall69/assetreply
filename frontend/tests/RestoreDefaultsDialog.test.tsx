/**
 * 기본값 복원 확인창 테스트 (T049) — contracts/ui-wireframes.md W4-a.
 *
 * FR-032: 되돌리기 전에 **무엇이 어떻게 바뀌는지** 보여주고 확인을 받는다.
 * "정말 하시겠습니까?"만 묻는 확인창은 사용자가 결과를 모른 채 누르게 한다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { RestoreDefaultsDialog } from "@/components/settings/RestoreDefaultsDialog";

const CURRENT = { cashBuy: "0.002500", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" };
const DEFAULT = { cashBuy: "0.001800", cashSell: "0.001800", remitSend: "0.000500", remitReceive: "0.000500" };

const props = {
  scope: "USD" as const, current: CURRENT, defaults: DEFAULT,
  onConfirm: vi.fn(), onCancel: vi.fn(),
};

describe("기본값 복원 확인창", () => {
  it("복원 범위를 밝힌다", () => {
    render(<RestoreDefaultsDialog {...props} />);
    expect(screen.getByRole("dialog").textContent).toContain("USD");
  });

  it("전체 복원 범위도 밝힌다", () => {
    render(<RestoreDefaultsDialog {...props} scope="all" />);
    expect(screen.getByRole("dialog").textContent).toContain("전 통화");
  });

  it("바뀌는 값을 전후로 보여준다", () => {
    render(<RestoreDefaultsDialog {...props} />);
    const row = screen.getByTestId("diff-cashBuy");
    expect(row.textContent).toContain("0.002500");
    expect(row.textContent).toContain("0.001800");
  });

  it("변화 없는 항목을 표시한다", () => {
    render(<RestoreDefaultsDialog {...props} />);
    expect(screen.getByTestId("diff-cashSell").textContent).toContain("변화 없음");
  });

  it("입력값을 잃는다는 사실을 알린다", () => {
    render(<RestoreDefaultsDialog {...props} />);
    expect(screen.getByText(/현재 입력값은 사라집니다/)).toBeInTheDocument();
  });

  it("취소하면 확인 콜백이 호출되지 않는다", async () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<RestoreDefaultsDialog {...props} onConfirm={onConfirm} onCancel={onCancel} />);
    await userEvent.click(screen.getByRole("button", { name: "취소" }));
    expect(onCancel).toHaveBeenCalled();
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("되돌리기를 눌러야 확인된다", async () => {
    const onConfirm = vi.fn();
    render(<RestoreDefaultsDialog {...props} onConfirm={onConfirm} />);
    await userEvent.click(screen.getByRole("button", { name: "되돌리기" }));
    expect(onConfirm).toHaveBeenCalled();
  });
});
