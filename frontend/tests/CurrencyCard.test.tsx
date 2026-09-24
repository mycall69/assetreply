/**
 * 통화 카드 검증 (T037) — FR-006a, FR-016, FR-029, SC-006.
 *
 * **"지금 하실 일은 없습니다"가 FR-006a의 요구다.** 경고만 띄우고 설명이 없으면
 * 사용자는 자기가 뭔가 해야 한다고 오해한다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CurrencyCard } from "@/components/collection/CurrencyCard";
import type { JobDisplayState, TimelineSnapshot } from "@/lib/types";

const BASE: TimelineSnapshot = {
  generatedAt: "2026-09-24T10:00:00", callsToday: 12, currency: "USD",
  targetFrom: "2020-01-01", targetTo: "2024-12-31",
  coveredFrom: "2020-01-01", coveredThrough: "2022-12-31", busyWith: null,
};

function withState(state: JobDisplayState): TimelineSnapshot {
  return {
    ...BASE,
    activeJob: {
      jobId: 1, rangeStart: "2023-01-01", chunksTotal: 2, chunksDone: 1,
      currentChunk: { from: "2023-01-01", to: "2023-12-31" }, state,
    },
  };
}

describe("상태 배지", () => {
  it("진행 중", () => {
    render(<CurrencyCard snapshot={withState("running")} onStart={vi.fn()} />);
    expect(screen.getByText("진행 중")).toBeTruthy();
  });

  it("응답 없음", () => {
    render(<CurrencyCard snapshot={withState("stalled")} onStart={vi.fn()} />);
    expect(screen.getByText(/응답 없음/)).toBeTruthy();
  });

  it("회수 대기", () => {
    render(<CurrencyCard snapshot={withState("awaiting_reclaim")} onStart={vi.fn()} />);
    expect(screen.getByText(/회수 대기/)).toBeTruthy();
  });

  it("수집 이력 없음", () => {
    render(<CurrencyCard snapshot={{ ...BASE, coveredFrom: null, coveredThrough: null }} onStart={vi.fn()} />);
    expect(screen.getByText("수집 이력 없음")).toBeTruthy();
  });

  it("완료", () => {
    render(<CurrencyCard snapshot={{ ...BASE, coveredThrough: "2024-12-31" }} onStart={vi.fn()} />);
    expect(screen.getByText("완료")).toBeTruthy();
  });
});

describe("멈춤 설명", () => {
  it("stalled면 할 일이 없음을 알린다", () => {
    render(<CurrencyCard snapshot={withState("stalled")} onStart={vi.fn()} />);
    expect(screen.getByText(/지금 하실 일은 없습니다/)).toBeTruthy();
  });

  it("회수 대기에서도 알린다", () => {
    render(<CurrencyCard snapshot={withState("awaiting_reclaim")} onStart={vi.fn()} />);
    expect(screen.getByText(/지금 하실 일은 없습니다/)).toBeTruthy();
  });
});

describe("이어받기 식별 (SC-006)", () => {
  it("재개 지점이 설명에 드러난다", () => {
    // 시간축의 ▲ 캡션(W2)과 카드 설명(W3) 양쪽에 나온다. 와이어프레임이 둘 다
    // 명시한 의도된 중복이라 개수로 검증한다.
    render(<CurrencyCard snapshot={withState("running")} onStart={vi.fn()} />);
    expect(screen.getAllByText(/2023-01-01부터 이어받는 중/).length).toBeGreaterThanOrEqual(1);
  });

  it("처음부터 받으면 재개 문구가 없다", () => {
    render(<CurrencyCard snapshot={{
      ...BASE, coveredFrom: null, coveredThrough: null,
      activeJob: { jobId: 1, rangeStart: "2020-01-01", chunksTotal: 5, chunksDone: 0,
                   currentChunk: null, state: "running" },
    }} onStart={vi.fn()} />);
    expect(screen.queryByText(/이어받는 중/)).toBeNull();
  });
});

describe("조작", () => {
  it("진행 중이면 버튼을 내보내지 않는다 (FR-016)", () => {
    render(<CurrencyCard snapshot={withState("running")} onStart={vi.fn()} />);
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("일부 받았으면 이어받기다", () => {
    render(<CurrencyCard snapshot={BASE} onStart={vi.fn()} />);
    expect(screen.getByRole("button").textContent).toBe("이어받기");
  });

  it("처음이면 수집 시작이다", () => {
    render(<CurrencyCard snapshot={{ ...BASE, coveredFrom: null, coveredThrough: null }} onStart={vi.fn()} />);
    expect(screen.getByRole("button").textContent).toBe("수집 시작");
  });

  it("다른 통화가 돌면 막고 이유를 댄다 (FR-029)", () => {
    render(<CurrencyCard snapshot={{ ...BASE, busyWith: "JPY" }} onStart={vi.fn()} />);
    expect(screen.getByRole("button").hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/JPY를 수집하는 중입니다/)).toBeTruthy();
  });
});
