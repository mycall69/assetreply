/**
 * 예금 투자처 고르기 — 체크박스 (013 T017) — FR-003, FR-004, ui-wireframes F2.
 *
 * 메뉴의 투자처 고르기(`InstitutionPicker`)는 라디오(하나)다. 비교는 여러 투자처를 고른다. 정기 적금이면 적금이 없는 투자처는
 * 끈다 — 이미 고른 곳은 체크를 남기고 까닭을 보인다(실행하면 막힘으로 드러난다 — FR-010).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InstitutionChecklist } from "@/components/compare/InstitutionChecklist";
import type { DepositInstitution, DepositInstitutionKey } from "@/lib/types";

const available = { available: true, description: "정기적금(1-2년)", firstMonth: "2012-01", latestMonth: "2026-08",
  checkedOn: "2026-10-04", startableFrom: "2011-01-01" } as const;
const missing = { available: false, reason: "출처에 적금 항목이 없습니다" } as const;

const institution = (key: DepositInstitutionKey, name: string, installment: object): DepositInstitution => ({
  key, name, description: `${name} 정기예금`, firstMonth: "2012-01", latestMonth: "2026-08", checkedOn: "2026-10-04",
  installment: installment as DepositInstitution["installment"],
});

const LIST: DepositInstitution[] = [
  institution("commercial_bank", "시중은행", available),
  institution("savings_bank", "저축은행", missing),
  institution("credit_union", "신협", missing),
  institution("mutual_finance", "상호금융", available),
  institution("saemaul", "새마을금고", missing),
];

describe("InstitutionChecklist", () => {
  it("다섯 투자처가 체크박스다", () => {
    render(<InstitutionChecklist institutions={LIST} selected={["commercial_bank"]} product="deposit"
      onToggle={() => undefined} />);
    const boxes = screen.getAllByRole("checkbox");
    expect(boxes).toHaveLength(5);
    expect(screen.getByRole("checkbox", { name: /시중은행/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /저축은행/ })).not.toBeChecked();
  });

  it("체크하면 더하고 풀면 뺀다", () => {
    const onToggle = vi.fn();
    render(<InstitutionChecklist institutions={LIST} selected={["commercial_bank"]} product="deposit" onToggle={onToggle} />);
    fireEvent.click(screen.getByRole("checkbox", { name: /신협/ }));
    fireEvent.click(screen.getByRole("checkbox", { name: /시중은행/ }));
    expect(onToggle.mock.calls).toEqual([["credit_union", true], ["commercial_bank", false]]);
  });

  it("목록을 받기 전에도 이름으로 그린다", () => {
    render(<InstitutionChecklist institutions={null} selected={[]} product="deposit" onToggle={() => undefined} />);
    expect(screen.getAllByRole("checkbox")).toHaveLength(5);
    expect(screen.getByRole("checkbox", { name: /새마을금고/ })).toBeEnabled();
  });

  it("정기 적금이면 적금이 없는 투자처는 꺼지고 까닭이 보인다", () => {
    render(<InstitutionChecklist institutions={LIST} selected={[]} product="installment" onToggle={() => undefined} />);
    expect(screen.getByRole("checkbox", { name: /저축은행/ })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /상호금융/ })).toBeEnabled();
    expect(screen.getAllByText(/정기 적금이 없는 투자처/).length).toBeGreaterThan(0);
  });

  it("이미 고른 곳은 정기 적금으로 바꿔도 체크가 남고 까닭이 보인다 — 풀 수 있다", () => {
    const onToggle = vi.fn();
    render(<InstitutionChecklist institutions={LIST} selected={["savings_bank"]} product="installment" onToggle={onToggle} />);
    const box = screen.getByRole("checkbox", { name: /저축은행/ });
    expect(box).toBeChecked();
    expect(box).toBeEnabled();
    fireEvent.click(box);
    expect(onToggle).toHaveBeenCalledWith("savings_bank", false);
  });

  it("메뉴의 라디오와 이름·id가 겹치지 않는다", () => {
    const { container } = render(<InstitutionChecklist institutions={LIST} selected={[]} product="deposit"
      onToggle={() => undefined} />);
    expect(container.querySelector('[name="deposit-institution"]')).toBeNull();
    expect(container.querySelector('[id^="deposit-inst-"]')).toBeNull();
  });
});
