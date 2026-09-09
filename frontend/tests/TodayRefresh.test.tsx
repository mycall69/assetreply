/**
 * 오늘 새로고침 UI 테스트 (T062) — contracts/ui-wireframes.md W3-b·W3-c.
 *
 * FR-038: 마지막으로 받아온 시각을 표시한다.
 * FR-039: 오늘 고시가 없으면 그 사실을 알린다.
 * FR-040: **실패해도 이미 표시 중인 값을 지우지 않는다.** 화면을 비우면 사용자는
 * 가진 정보까지 잃는다.
 */
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TodayRefresh } from "@/components/fx/TodayRefresh";
import { ApiError, apiClient } from "@/lib/apiClient";

describe("오늘 새로고침", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("버튼을 누르면 오늘 하루치를 요청한다", async () => {
    const post = vi.spyOn(apiClient, "post").mockResolvedValue({
      currency: "USD", status: "updated", date: "2026-08-30",
      baseRate: "1354.200000", isProvisional: true,
      fetchedAt: "2026-08-30T14:23:11Z", joinedExisting: false,
    });
    render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    expect(post).toHaveBeenCalledWith("/api/fx/today/refresh", { currency: "USD" });
  });

  it("갱신 후 부모에게 알린다", async () => {
    vi.spyOn(apiClient, "post").mockResolvedValue({
      currency: "USD", status: "updated", date: "2026-08-30",
      fetchedAt: "2026-08-30T14:23:11Z", joinedExisting: false,
    });
    const onRefreshed = vi.fn();
    render(<TodayRefresh currency="USD" onRefreshed={onRefreshed} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    expect(onRefreshed).toHaveBeenCalled();
  });

  it("오늘 고시가 없으면 그 사실을 알린다", async () => {
    vi.spyOn(apiClient, "post").mockResolvedValue({
      currency: "USD", status: "no_quote_today", date: "2026-08-30",
      message: "오늘은 아직 고시가 없습니다.",
      fetchedAt: "2026-08-30T14:23:11Z", joinedExisting: false,
    });
    render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    expect(await screen.findByText(/아직 고시가 없습니다/)).toBeInTheDocument();
  });

  it("실패하면 사유를 알리되 화면을 비우지 않는다", async () => {
    vi.spyOn(apiClient, "post").mockRejectedValue(
      new ApiError(503, "source_unavailable", "데이터 제공처 응답 없음"),
    );
    render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("데이터 제공처 응답 없음");
    // 버튼은 그대로 남아 재시도할 수 있어야 한다
    expect(screen.getByRole("button", { name: /새로고침/ })).toBeInTheDocument();
  });

  it("진행 중에는 중복 요청을 막는다", async () => {
    let resolve: (v: never) => void = () => {};
    const post = vi.spyOn(apiClient, "post").mockReturnValue(
      new Promise<never>((r) => { resolve = r; }),
    );
    render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);
    const button = screen.getByRole("button", { name: /새로고침/ });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(post).toHaveBeenCalledTimes(1);
    resolve(undefined as never);
  });
});

describe("새로고침 중 통화 변경 (FR-036c)", () => {
  beforeEach(() => vi.restoreAllMocks());

  /** 요청은 시작 시점의 통화에 귀속된다. 늦게 도착한 결과가 다른 통화 화면을 건드리면 안 된다. */
  it("통화가 바뀌면 늦게 온 결과를 화면에 반영하지 않는다", async () => {
    let resolve: (v: never) => void = () => {};
    vi.spyOn(apiClient, "post").mockReturnValue(
      new Promise<never>((r) => { resolve = r; }),
    );
    const onRefreshed = vi.fn();
    const { rerender } = render(
      <TodayRefresh currency="USD" onRefreshed={onRefreshed} />,
    );

    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    // 응답이 오기 전에 사용자가 통화를 바꾼다
    rerender(<TodayRefresh currency="JPY" onRefreshed={onRefreshed} />);

    await act(async () => {
      resolve({
        currency: "USD", status: "no_quote_today", date: "2026-08-30",
        message: "오늘은 아직 고시가 없습니다.",
        fetchedAt: "2026-08-30T14:23:11Z", joinedExisting: false,
      } as never);
    });

    expect(screen.queryByText(/아직 고시가 없습니다/)).toBeNull();
    expect(onRefreshed).not.toHaveBeenCalled();
  });

  it("통화가 바뀌면 늦게 온 실패도 반영하지 않는다", async () => {
    let reject: (e: unknown) => void = () => {};
    vi.spyOn(apiClient, "post").mockReturnValue(
      new Promise<never>((_, r) => { reject = r; }),
    );
    const { rerender } = render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);

    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    rerender(<TodayRefresh currency="JPY" onRefreshed={vi.fn()} />);

    await act(async () => {
      reject(new ApiError(503, "source_unavailable", "데이터 제공처 응답 없음"));
    });

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("통화가 그대로면 결과를 반영한다", async () => {
    vi.spyOn(apiClient, "post").mockResolvedValue({
      currency: "USD", status: "no_quote_today", date: "2026-08-30",
      message: "오늘은 아직 고시가 없습니다.",
      fetchedAt: "2026-08-30T14:23:11Z", joinedExisting: false,
    });
    const onRefreshed = vi.fn();
    render(<TodayRefresh currency="USD" onRefreshed={onRefreshed} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));

    expect(await screen.findByText(/아직 고시가 없습니다/)).toBeInTheDocument();
    expect(onRefreshed).toHaveBeenCalled();
  });

  it("통화가 바뀌어도 버튼은 다시 누를 수 있다", async () => {
    let resolve: (v: never) => void = () => {};
    vi.spyOn(apiClient, "post").mockReturnValue(
      new Promise<never>((r) => { resolve = r; }),
    );
    const { rerender } = render(<TodayRefresh currency="USD" onRefreshed={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: /새로고침/ }));
    rerender(<TodayRefresh currency="JPY" onRefreshed={vi.fn()} />);

    await act(async () => { resolve(undefined as never); });

    // busy가 풀려야 새 통화로 다시 받을 수 있다
    expect(screen.getByRole("button", { name: /새로고침/ })).not.toBeDisabled();
  });
});
