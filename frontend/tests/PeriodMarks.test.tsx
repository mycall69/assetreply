/**
 * 주식·가상자산 표의 기간 표시와 범례 (012 T020) — FR-004, FR-004a, FR-010, contracts/ui-wireframes.md F3.
 *
 * - 📅 = 기준일이 옮겨졌다(그날 시세·일봉이 없어 다른 날 값이다), ⏳ = 구간이 아직 끝나지 않았다. 둘은 서로 다른 사실이고 한 행에 함께 붙을 수 있다
 *   (004 FR-015b와 같다)
 * - 기호만으로 전달하지 않는다 — 기호마다 `title`·`aria-label` 글자 설명이 있다. 문구는 외환 `PeriodRowBadges`의 모양을 따르되 "시세"(주식)·"일봉"
 *   (가상자산)이다
 * - 표시가 없는 행과 일 단위에는 아무것도 그리지 않는다. 범례는 주·월에만 있다
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PeriodLegend } from "@/components/period/PeriodLegend";
import { PeriodMarks } from "@/components/period/PeriodMarks";

describe("기간 표시", () => {
  it("주식 주 단위 — 옮겨짐과 진행 중을 각각 글자로 말한다", () => {
    render(<PeriodMarks row={{ date: "2026-10-12", shiftedFrom: "2026-10-16", isOngoing: true }} unit="weekly" asset="stock" />);
    expect(screen.getByRole("img", { name: "기준일 2026-10-16(금)에 시세가 없어 2026-10-12 값입니다" })).toHaveTextContent("📅");
    expect(screen.getByRole("img", { name: "이번 주가 아직 끝나지 않았습니다" })).toHaveTextContent("⏳");
  });

  it("가상자산 월 단위 — 일봉이고 말일이다", () => {
    render(<PeriodMarks row={{ date: "2021-03-21", shiftedFrom: "2021-03-31", isOngoing: true }} unit="monthly" asset="crypto" />);
    expect(screen.getByRole("img", { name: "기준일 2021-03-31(말일)에 일봉이 없어 2021-03-21 값입니다" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "이번 달이 아직 끝나지 않았습니다" })).toBeInTheDocument();
  });

  it("title과 aria-label이 같다 — 마우스로도 읽힌다", () => {
    render(<PeriodMarks row={{ date: "2026-10-08", shiftedFrom: "2026-10-09" }} unit="weekly" asset="stock" />);
    const mark = screen.getByRole("img");
    expect(mark.getAttribute("title")).toBe(mark.getAttribute("aria-label"));
  });

  it("옮겨지지 않았고 끝난 구간이면 아무것도 그리지 않는다", () => {
    const { container } = render(<PeriodMarks row={{ date: "2026-10-02" }} unit="weekly" asset="stock" />);
    expect(container).toBeEmptyDOMElement();
  });

  it("일 단위에는 표시가 없다", () => {
    const { container } = render(
      <PeriodMarks row={{ date: "2026-10-12", shiftedFrom: "2026-10-16", isOngoing: true }} unit="daily" asset="stock" />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("범례", () => {
  it("주·월에는 두 표시의 뜻을 글로 둔다", () => {
    for (const unit of ["weekly", "monthly"] as const) {
      const { unmount } = render(<PeriodLegend unit={unit} />);
      expect(screen.getByText("📅 기준일이 옮겨진 행")).toBeInTheDocument();
      expect(screen.getByText("⏳ 아직 끝나지 않은 구간")).toBeInTheDocument();
      unmount();
    }
  });

  it("일 단위에는 범례가 없다", () => {
    const { container } = render(<PeriodLegend unit="daily" />);
    expect(container).toBeEmptyDOMElement();
  });
});
