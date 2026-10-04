/**
 * 예금 보드 아래 안내 줄 (T016) — 008 FR-007, FR-016, FR-024, SC-005, ui-wireframes D3.
 *
 * 잠정 줄은 **잠정 시작일, 대신 쓴 금리의 달과 값, "발표되면 값이 바뀐다"**를 모두 담는다(SC-005) — 하나라도 빠지면 사용자가
 * 잠정 값을 확정 값으로 읽는다. 멈춤 줄은 어느 달이 비어 어느 만기에서 멈췄는지를 말한다. 확인 실패 줄은 받아 둔 금리로
 * 계산했다는 사실과 사유다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { DepositNotice } from "@/components/deposit/DepositNotice";
import type { DepositSummary } from "@/lib/types";
import { PROVISIONAL, RESULT } from "./support/depositFixtures";

const STOPPED: DepositSummary = {
  ...RESULT.summary, isFinal: false, asOf: "2024-03-15", currentTerm: null,
  stopped: { date: "2024-03-15", reason: "rate_missing", month: "2024-03" },
};

describe("예금 안내 줄", () => {
  it("확정 결과면 아무것도 보이지 않는다", () => {
    const { container } = render(<DepositNotice summary={RESULT.summary} start="2020-01-15" />);
    expect(container.textContent).toBe("");
  });

  it("잠정 — 시작일·대신 쓴 달과 값·발표되면 바뀐다는 사실", () => {
    render(<DepositNotice summary={PROVISIONAL.summary} start="2026-09-15" />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("잠정");
    expect(line).toContain("2026-09-15 가입");
    expect(line).toContain("2026-08 금리(3.39%)");
    expect(line).toContain("금리가 발표되면 값이 바뀝니다");
  });

  it("재예치에서 잠정이 시작되면 재예치라고 쓴다", () => {
    const summary: DepositSummary = { ...PROVISIONAL.summary, provisionalFrom: "2026-01-15",
      currentTerm: { ...PROVISIONAL.summary.currentTerm!, joinedOn: "2026-01-15" } };
    render(<DepositNotice summary={summary} start="2020-01-15" />);
    expect(screen.getByRole("status").textContent).toContain("2026-01-15 재예치");
  });

  it("멈춤 — 빈 달과 멈춘 만기일", () => {
    render(<DepositNotice summary={STOPPED} start="2020-01-15" />);
    const line = screen.getByRole("status").textContent ?? "";
    expect(line).toContain("2024-03 금리 통계가 비어 있어 2024-03-15 만기에서 계산을 멈췄습니다");
    expect(line).toContain("그날까지의 결과입니다");
  });

  it("오늘 확인이 실패했으면 사유와 받아 둔 금리로 계산했다는 사실", () => {
    const summary: DepositSummary = { ...PROVISIONAL.summary,
      recheckFailed: { kind: "network", reason: "출처에 연결하지 못했습니다" } };
    render(<DepositNotice summary={summary} start="2026-09-15" />);
    const text = screen.getAllByRole("status").map((s) => s.textContent).join(" ");
    expect(text).toContain("오늘 금리 확인에 실패했습니다(출처에 연결하지 못했습니다)");
    expect(text).toContain("받아 둔 금리로 계산했습니다");
    expect(text).toContain("내일 다시 확인합니다");
  });
});
