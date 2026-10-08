/**
 * 이력 칸 상태의 빈 목록 문구 (013 T064) — ui-wireframes F9.
 *
 * 저장한 비교 칸이 `HistoryContent`를 함께 쓴다 — 빈 목록 문구만 다르다. 속성을 주지 않으면 지금 문구 그대로다(메뉴 이력 화면 불변).
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { HistoryContent } from "@/components/history/HistoryStates";

describe("HistoryContent 빈 목록 문구", () => {
  it("속성이 없으면 지금 문구다", () => {
    render(<HistoryContent empty>{null}</HistoryContent>);
    expect(screen.getByText("아직 실행한 시뮬레이션이 없습니다.")).toBeInTheDocument();
  });

  it("주면 그 문구다", () => {
    render(<HistoryContent empty emptyText="아직 저장한 비교가 없습니다.">{null}</HistoryContent>);
    expect(screen.getByText("아직 저장한 비교가 없습니다.")).toBeInTheDocument();
    expect(screen.queryByText("아직 실행한 시뮬레이션이 없습니다.")).toBeNull();
  });

  it("불러오는 중·실패에는 빈 문구를 보이지 않는다(주어도)", () => {
    const { rerender } = render(
      <HistoryContent empty loading emptyText="아직 저장한 비교가 없습니다.">{null}</HistoryContent>);
    expect(screen.queryByText("아직 저장한 비교가 없습니다.")).toBeNull();
    rerender(<HistoryContent empty loadError="목록을 받지 못했습니다" emptyText="아직 저장한 비교가 없습니다.">{null}</HistoryContent>);
    expect(screen.queryByText("아직 저장한 비교가 없습니다.")).toBeNull();
  });
});
