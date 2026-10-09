/**
 * 대시보드 머리 (014 T025) — FR-002, FR-008, contracts D1.
 *
 * 오늘 날짜는 한국 시간이고, 화면을 열어 둔 채 한국 자정을 넘기면 바뀐다. [새로고침]은 지표 시세를 곧바로 다시 부른다(U3).
 */
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TodayHeader } from "@/components/dashboard/TodayHeader";

describe("오늘 날짜", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-10-09T14:59:50Z")); // 한국 23:59:50
  });
  afterEach(() => vi.useRealTimers());

  it("한국 자정을 넘기면 날짜가 바뀐다", async () => {
    render(<TodayHeader fetchedAt={null} onRefresh={vi.fn()} />);
    expect(screen.getByTestId("today")).toHaveTextContent("2026년 10월 9일 (금)");
    await act(async () => {
      vi.advanceTimersByTime(11_000);
    });
    expect(screen.getByTestId("today")).toHaveTextContent("2026년 10월 10일 (토)");
    expect(screen.getByText("한국 시간")).toBeInTheDocument();
  });
});

describe("받은 시각과 새로고침", () => {
  it("받은 시각(한국)과 [새로고침]", () => {
    const onRefresh = vi.fn();
    render(<TodayHeader fetchedAt="2026-10-09T04:12:00Z" onRefresh={onRefresh} />);
    expect(screen.getByText("13:12 받음")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "새로고침" }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
