/**
 * 시간축 막대 검증 (T036) — FR-011, FR-012, FR-013, FR-014.
 *
 * **이어받기 표식이 이 화면의 핵심 요구다.** 없으면 사용자는 이어받기가 동작했는지
 * 판단할 수 없다. 처음부터 받는 경우에는 두지 않는다 — 늘 있으면 의미가 사라진다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { CurrencyTimeline } from "@/components/collection/CurrencyTimeline";
import type { TimelineSnapshot } from "@/lib/types";

const BASE: TimelineSnapshot = {
  generatedAt: "2026-09-24T10:00:00",
  callsToday: 12,
  currency: "USD",
  targetFrom: "2020-01-01",
  targetTo: "2024-12-31",
  coveredFrom: "2020-01-01",
  coveredThrough: "2022-12-31",
  busyWith: null,
};

describe("구간 구별", () => {
  it("완료 구간을 그린다", () => {
    render(<CurrencyTimeline snapshot={BASE} />);
    expect(screen.getByTestId("covered")).toBeTruthy();
  });

  it("수집 이력이 없으면 완료 구간이 없다", () => {
    render(<CurrencyTimeline snapshot={{ ...BASE, coveredFrom: null, coveredThrough: null }} />);
    expect(screen.queryByTestId("covered")).toBeNull();
  });

  it("진행 중 구간을 완료와 구별해 그린다", () => {
    render(<CurrencyTimeline snapshot={{
      ...BASE,
      activeJob: {
        jobId: 1, rangeStart: "2023-01-01", chunksTotal: 2, chunksDone: 0,
        currentChunk: { from: "2023-01-01", to: "2023-12-31" }, state: "running",
      },
    }} />);
    expect(screen.getByTestId("current-chunk")).toBeTruthy();
    expect(screen.getByTestId("covered")).toBeTruthy();
  });

  it("진행 중이 아니면 진행 구간을 내보내지 않는다", () => {
    render(<CurrencyTimeline snapshot={BASE} />);
    expect(screen.queryByTestId("current-chunk")).toBeNull();
  });
});

describe("이어받기 표식", () => {
  it("이어받았으면 표식이 있다", () => {
    render(<CurrencyTimeline snapshot={{
      ...BASE,
      activeJob: {
        jobId: 1, rangeStart: "2023-01-01", chunksTotal: 2, chunksDone: 0,
        currentChunk: { from: "2023-01-01", to: "2023-12-31" }, state: "running",
      },
    }} />);
    expect(screen.getByTestId("resume-marker")).toBeTruthy();
    expect(screen.getByText(/2023-01-01부터 이어받는 중/)).toBeTruthy();
  });

  it("처음부터 받으면 표식이 없다", () => {
    render(<CurrencyTimeline snapshot={{
      ...BASE, coveredFrom: null, coveredThrough: null,
      activeJob: {
        jobId: 1, rangeStart: "2020-01-01", chunksTotal: 5, chunksDone: 0,
        currentChunk: { from: "2020-01-01", to: "2020-12-30" }, state: "running",
      },
    }} />);
    expect(screen.queryByTestId("resume-marker")).toBeNull();
  });
});

describe("접근성", () => {
  it("진행률 텍스트 대체가 있다", () => {
    render(<CurrencyTimeline snapshot={BASE} />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/수집 완료/);
  });

  it("수집 전에도 상태를 읽을 수 있다", () => {
    render(<CurrencyTimeline snapshot={{ ...BASE, coveredFrom: null, coveredThrough: null }} />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/아직 수집하지 않았습니다/);
  });
});
