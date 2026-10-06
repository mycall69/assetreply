/**
 * 적금의 투자처 고르기 (011 T045) — FR-023, FR-029, ui-wireframes §7.
 *
 * - 정기 적금이면 출처에 적금 항목이 없는 셋(저축은행·신협·새마을금고)은 `disabled`이고, 사유를 `aria-describedby`로 잇는다 — 정기예금
 *   금리로 대신하지 않는다
 * - 고른 투자처의 설명 줄은 적금 상품 범위와 시작 가능 날짜다("2011-01-01부터 가입할 수 있습니다"). 받기 전에는 날짜를 지어내지 않는다
 * - 정기예금(기본)이면 지금 동작 그대로다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { InstitutionPicker } from "@/components/deposit/InstitutionPicker";
import { INSTALLMENT_INSTITUTIONS, UNAVAILABLE_REASON } from "./support/installmentFixtures";

const LIST = INSTALLMENT_INSTITUTIONS.institutions;

describe("적금의 투자처", () => {
  it("적금 통계가 없는 셋은 고를 수 없고 사유가 이어진다", () => {
    render(<InstitutionPicker institutions={LIST} value="commercial_bank" product="installment" onChange={vi.fn()} />);
    for (const name of ["저축은행", "신협", "새마을금고"]) {
      const radio = screen.getByRole("radio", { name });
      expect(radio).toBeDisabled();
      const describedBy = radio.getAttribute("aria-describedby");
      expect(describedBy).not.toBeNull();
      expect(document.getElementById(describedBy as string)).toHaveTextContent(UNAVAILABLE_REASON);
    }
    expect(screen.getByRole("radio", { name: "시중은행" })).toBeEnabled();
    expect(screen.getByRole("radio", { name: "상호금융" })).toBeEnabled();
  });

  it("고른 투자처의 설명 줄은 적금 상품 범위와 시작 가능 날짜다", () => {
    render(<InstitutionPicker institutions={LIST} value="commercial_bank" product="installment" onChange={vi.fn()} />);
    expect(screen.getByText("예금은행 정기적금(1~2년 만기) 평균 · 2011-01-01부터 가입할 수 있습니다")).toBeInTheDocument();
  });

  it("받기 전이면 시작 가능 날짜를 말하지 않는다", () => {
    render(<InstitutionPicker institutions={LIST} value="mutual_finance" product="installment" onChange={vi.fn()} />);
    expect(screen.getByText("상호금융 정기적금 평균 — 만기 구분 없음")).toBeInTheDocument();
    expect(screen.queryByText(/가입할 수 있습니다/)).toBeNull();
  });

  it("정기예금이면 지금 동작 그대로다", () => {
    render(<InstitutionPicker institutions={LIST} value="commercial_bank" onChange={vi.fn()} />);
    expect(screen.getAllByRole("radio").every((r) => !(r as HTMLInputElement).disabled)).toBe(true);
    expect(screen.getByText("예금은행 정기예금(1년) 평균 — 일반·특수은행 포함 · 2012-01부터")).toBeInTheDocument();
  });
});
