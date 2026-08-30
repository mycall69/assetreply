/**
 * 수집 진행 화면 테스트 (T092) — contracts/ui-sketches.md S4.
 *
 * FR-013: 중단 화면은 **이미 저장된 구간이 유효함**을 반드시 알려야 한다.
 * 이 문장이 없으면 사용자는 전부 실패한 것으로 보고 처음부터 다시 돌린다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CollectionProgress } from "@/components/CollectionProgress";
import type { ProgressState } from "@/lib/types";

const RUNNING: ProgressState = {
  jobId: 42, currency: "USD", status: "running",
  chunksTotal: 32, chunksDone: 18,
  currentRange: { from: "2013-01-01", to: "2013-12-31" },
  coveredThrough: "2012-12-31", lastError: null,
};

const PARTIAL: ProgressState = {
  ...RUNNING, status: "partial",
  lastError: "호출 한도 초과(INFO-300)가 반복되어 중단했습니다.",
};

describe("진행 중", () => {
  it("진행률을 표시한다", () => {
    render(<CollectionProgress state={RUNNING} />);
    expect(screen.getByText(/18\s*\/\s*32/)).toBeInTheDocument();
  });

  it("현재 구간과 완료 구간을 표시한다", () => {
    render(<CollectionProgress state={RUNNING} />);
    expect(screen.getByText(/2013-01-01/)).toBeInTheDocument();
    expect(screen.getByText(/2012-12-31/)).toBeInTheDocument();
  });

  it("진행 바에 접근 가능한 값을 준다", () => {
    render(<CollectionProgress state={RUNNING} />);
    const bar = screen.getByRole("progressbar");
    expect(bar).toHaveAttribute("aria-valuenow", "18");
    expect(bar).toHaveAttribute("aria-valuemax", "32");
  });
});

describe("중단됨", () => {
  it("중단 사유를 표시한다", () => {
    render(<CollectionProgress state={PARTIAL} />);
    expect(screen.getByText(/INFO-300/)).toBeInTheDocument();
  });

  it("이미 저장된 구간이 유효함을 알린다", () => {
    render(<CollectionProgress state={PARTIAL} />);
    expect(screen.getByText(/조회할 수 있습니다/)).toBeInTheDocument();
  });

  it("완료 구간을 함께 보여준다", () => {
    render(<CollectionProgress state={PARTIAL} />);
    expect(screen.getByText(/2012-12-31/)).toBeInTheDocument();
  });

  it("다시 시도 버튼을 제공한다", () => {
    render(<CollectionProgress state={PARTIAL} onRetry={() => {}} />);
    expect(screen.getByRole("button", { name: /다시 시도/ })).toBeInTheDocument();
  });
});
