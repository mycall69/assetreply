/**
 * 수집 현황 진입점 검증 (T090) — FR-030, SC-018.
 *
 * **이 테스트가 깨지면 기능 전체가 도달 불가능해진다.**
 *
 * 사이드바에 수집 현황이 없고, `/fx/collection`으로 가는 링크는 이 표시기 하나뿐이다.
 * 표시기가 진행 중일 때만 나타나면 다음 고리가 닫힌다.
 *
 *   수집이 안 돌고 있다 → 표시기가 안 보인다 → 수집 현황에 갈 수 없다
 *          ↑                                            │
 *          └────────  수집 시작 버튼을 못 누른다  ←──────┘
 */
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CollectionIndicator } from "@/components/shell/CollectionIndicator";

const originalFetch = globalThis.fetch;

function mockJobs(jobs: Array<{ currency: string; status: string }>) {
  globalThis.fetch = vi.fn(async () =>
    new Response(JSON.stringify({ jobs }), {
      status: 200,
      headers: { "content-type": "application/json" },
    }),
  ) as unknown as typeof fetch;
}

beforeEach(() => vi.useRealTimers());
afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe("대기 상태", () => {
  it("진행 중인 수집이 없어도 렌더링된다", async () => {
    mockJobs([]);
    render(<CollectionIndicator pollMs={100_000} />);
    expect(await screen.findByRole("link")).toBeTruthy();
  });

  it("수집 현황으로 가는 링크를 갖는다", async () => {
    mockJobs([]);
    render(<CollectionIndicator pollMs={100_000} />);
    const link = await screen.findByRole("link");
    expect(link.getAttribute("href")).toBe("/fx/collection");
  });

  it("누를 수 있음이 문구로 드러난다", async () => {
    mockJobs([]);
    render(<CollectionIndicator pollMs={100_000} />);
    expect(await screen.findByText(/수집 현황/)).toBeTruthy();
  });

  it("조회에 실패해도 링크가 사라지지 않는다", async () => {
    // 표시기는 부가 정보지만 **유일한 진입점**이다. 조회 실패로 사라지면
    // 서버가 잠깐 불안정한 사이 기능 전체가 도달 불가능해진다.
    globalThis.fetch = vi.fn(async () => {
      throw new Error("연결 실패");
    }) as unknown as typeof fetch;
    render(<CollectionIndicator pollMs={100_000} />);
    expect(await screen.findByRole("link")).toBeTruthy();
  });
});

describe("진행 중 상태", () => {
  it("진행 중인 통화를 보여준다", async () => {
    mockJobs([{ currency: "USD", status: "running" }]);
    render(<CollectionIndicator pollMs={100_000} />);
    await waitFor(() => expect(screen.getByText(/USD/)).toBeTruthy());
  });

  it("진행 중에도 같은 링크를 유지한다", async () => {
    mockJobs([{ currency: "USD", status: "running" }]);
    render(<CollectionIndicator pollMs={100_000} />);
    const link = await screen.findByRole("link");
    expect(link.getAttribute("href")).toBe("/fx/collection");
  });
});
