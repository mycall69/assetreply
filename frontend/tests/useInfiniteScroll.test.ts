/**
 * 이어 보기 촉발 (T011) — 004 FR-001a, FR-005, SC-001b, SC-004.
 *
 * **스크롤 이벤트가 아니라 가시성을 신호로 삼는다.** 표가 화면보다 짧으면 스크롤이
 * 일어나지 않아, 스크롤을 기다리는 구현은 이어 보기를 **시도조차 하지 않는다**.
 * 실패 신호가 없어 사용자에게는 데이터가 그것뿐인 것과 구별되지 않는다 (FR-001a).
 *
 * 반대로 이미 불러오는 중에 또 부르면 오류 없이 성공하면서 같은 행을 두 번 그린다
 * (FR-005).
 */
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useInfiniteScroll } from "@/hooks/useInfiniteScroll";

type Entries = ReadonlyArray<{ isIntersecting: boolean }>;
type Observer = (entries: Entries) => void;

let observers: Observer[] = [];
let disconnected = 0;
const original = globalThis.IntersectionObserver;

class CapturingObserver {
  constructor(cb: Observer) {
    observers.push(cb);
  }
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {
    disconnected += 1;
  }
  takeRecords(): [] {
    return [];
  }
}

/** 감시 지점이 화면에 들어오거나 벗어난 상황을 만든다. */
function see(visible: boolean): void {
  act(() => {
    for (const cb of observers) cb([{ isIntersecting: visible }]);
  });
}

beforeEach(() => {
  observers = [];
  disconnected = 0;
  globalThis.IntersectionObserver =
    CapturingObserver as unknown as typeof IntersectionObserver;
});

afterEach(() => {
  globalThis.IntersectionObserver = original;
});

function mount(onLoadMore: () => void, enabled = true) {
  const view = renderHook(
    ({ on, en }: { on: () => void; en: boolean }) => useInfiniteScroll(on, en),
    { initialProps: { on: onLoadMore, en: enabled } },
  );
  act(() => {
    view.result.current(document.createElement("div"));
  });
  return view;
}

describe("이어 보기 촉발", () => {
  it("감시 지점이 보이면 스크롤 없이도 부른다", () => {
    // FR-001a — 표가 화면보다 짧아 스크롤이 일어나지 않는 경우가 이것이다.
    const onLoadMore = vi.fn();
    mount(onLoadMore);
    see(true);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it("보이지 않으면 부르지 않는다", () => {
    const onLoadMore = vi.fn();
    mount(onLoadMore);
    see(false);
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it("열려 있지 않으면 부르지 않는다", () => {
    // 불러오는 중이거나 끝에 도달한 상태. 중복 요청은 같은 행을 두 번 그린다 (SC-004).
    const onLoadMore = vi.fn();
    mount(onLoadMore, false);
    see(true);
    expect(onLoadMore).not.toHaveBeenCalled();
  });

  it("불러오기가 끝나고 여전히 보이면 다시 부른다", () => {
    // 표가 아직 화면보다 짧으면 채워질 때까지 이어져야 한다 (SC-001b).
    const onLoadMore = vi.fn();
    const view = mount(onLoadMore, true);
    see(true);
    expect(onLoadMore).toHaveBeenCalledTimes(1);

    view.rerender({ on: onLoadMore, en: false }); // 불러오는 중
    view.rerender({ on: onLoadMore, en: true }); // 도착
    expect(onLoadMore).toHaveBeenCalledTimes(2);
  });

  it("끝에 도달한 뒤에는 보여도 부르지 않는다", () => {
    // SC-003 — 더 받을 것이 없는데 계속 요청하면 안 된다.
    const onLoadMore = vi.fn();
    const view = mount(onLoadMore, true);
    see(true);
    view.rerender({ on: onLoadMore, en: false });
    see(true);
    see(false);
    see(true);
    expect(onLoadMore).toHaveBeenCalledTimes(1);
  });

  it("언마운트하면 관찰을 끊는다", () => {
    const view = mount(vi.fn());
    view.unmount();
    expect(disconnected).toBeGreaterThan(0);
  });
});
