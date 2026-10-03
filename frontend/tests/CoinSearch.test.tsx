/**
 * 코인 검색 (T016) — 007 FR-003~FR-006, FR-005b, ui-wireframes C2, analyze C2.
 *
 * - 한 줄: **한글 이름**(있으면) · 영문 이름 · 심볼 · 시세 통화 · 순위. 같은 심볼은 이름과 순위로 구별한다(FR-004)
 * - 엔터 = 맨 위, **한글 조합 중 엔터·방향키는 무시**(006 버그 `search-enter-ime`과 같은 테스트)
 * - **"결과 없음"과 "목록 없음"을 가른다** — 같은 빈 화면이 둘을 함께 뜻하면 할 일이 정반대인데 구별할 수 없다
 * - 목록을 처음 받거나 새로 받는 중이면 **진행 스트림을 구독해** 받은 쪽 수를 실시간으로 보인다. 끝나면 검색을 다시 보낸다
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import type { CoinListProgressHandlers } from "@/lib/cryptoListProgressStream";
import type { CoinListStatus } from "@/lib/types";
import {
  AS_OF,
  BTC,
  BTS,
  MAX_TOKEN,
  MAXCOIN,
  NEVER,
  READY,
  REFRESHING,
  response,
  routeSearch,
} from "./support/coinSearchFixtures";

// jsdom에는 `EventSource`가 없다. 구독은 `cryptoListProgressStream`의 책임이고, 여기서 보려는 것은 **언제 구독하고
// 받은 사건을 어떻게 보이는가**다.
const subscription = vi.hoisted(() => ({
  handlers: null as CoinListProgressHandlers | null,
  calls: 0,
  unsubscribe: vi.fn(),
}));
vi.mock("@/lib/cryptoListProgressStream", () => ({
  subscribeCoinListProgress: (handlers: CoinListProgressHandlers) => {
    subscription.handlers = handlers;
    subscription.calls += 1;
    return subscription.unsubscribe;
  },
}));

beforeEach(() => {
  vi.restoreAllMocks();
  subscription.handlers = null;
  subscription.calls = 0;
  subscription.unsubscribe = vi.fn();
});

async function typeIn(text: string) {
  const onSelect = vi.fn();
  const view = render(<CoinSearch value={null} onSelect={onSelect} />);
  await userEvent.type(screen.getByRole("searchbox"), text);
  return { onSelect, view };
}

describe("결과 한 줄", () => {
  it("한글 이름 · 영문 이름 · 심볼 · 통화 · 순위", async () => {
    routeSearch(() => Promise.resolve(response([BTC, BTS])));
    await typeIn("ㅂㅌ");
    const option = await screen.findByRole("option", { name: /비트코인/ });
    const text = option.textContent ?? "";
    expect(text).toContain("비트코인");
    expect(text).toContain("Bitcoin");
    expect(text).toContain("BTC · USD");
    expect(text).toContain("#1");
    expect(text.indexOf("비트코인")).toBeLessThan(text.indexOf("Bitcoin"));
  });

  it("한글 이름이 없으면 영문 이름이 맨 앞이다", async () => {
    routeSearch(() => Promise.resolve(response([BTS])));
    await typeIn("bts");
    const option = await screen.findByRole("option", { name: /BitShares/ });
    expect((option.textContent ?? "").startsWith("BitShares")).toBe(true);
    expect(option.textContent).toContain("#1,355");
  });

  it("같은 심볼은 이름과 순위로 구별되고 목록에서 빠진 코인은 글자로 알린다", async () => {
    routeSearch(() => Promise.resolve(response([MAX_TOKEN, MAXCOIN])));
    await typeIn("max");
    const options = await screen.findAllByRole("option");
    expect(options.map((o) => o.textContent ?? "")).toEqual([
      expect.stringContaining("#763"), expect.stringContaining("#5,359")]);
    expect(options[1].textContent).toContain("MaxCoin");
    expect(options[1].textContent).toContain("목록에서 빠짐");
    expect(options[0].textContent).not.toContain("목록에서 빠짐");
  });
});

describe("고르기", () => {
  it("엔터는 맨 위 결과를 고르고 칸을 비운다", async () => {
    routeSearch(() => Promise.resolve(response([BTC, BTS])));
    const { onSelect } = await typeIn("bit");
    await screen.findByRole("option", { name: /BitShares/ });
    await userEvent.keyboard("{Enter}");
    expect(onSelect).toHaveBeenCalledWith(BTC);
    expect(screen.getByRole("searchbox")).toHaveValue("");
  });

  it("방향키로 고른 항목이 있으면 그 항목이다", async () => {
    routeSearch(() => Promise.resolve(response([BTC, BTS])));
    const { onSelect } = await typeIn("bit");
    await screen.findByRole("option", { name: /BitShares/ });
    await userEvent.keyboard("{ArrowDown}{ArrowDown}{Enter}");
    expect(onSelect).toHaveBeenCalledWith(BTS);
  });

  it("고른 코인은 칸 아래에 이름과 심볼로 보인다", () => {
    routeSearch(() => Promise.resolve(response([])));
    render(<CoinSearch value={BTC} onSelect={vi.fn()} />);
    expect(screen.getByTestId("coin-selected").textContent).toContain("비트코인");
    expect(screen.getByTestId("coin-selected").textContent).toContain("BTC · USD");
  });
});

/** 006 버그 `search-enter-ime`과 같은 경로 — 조합 중 엔터에서 고르고 칸을 비우면 입력기가 마지막 글자를 빈 칸에 넣는다. */
describe("한글 조합 중", () => {
  async function composing() {
    routeSearch(() => Promise.resolve(response([BTC, BTS])));
    const onSelect = vi.fn();
    render(<CoinSearch value={null} onSelect={onSelect} />);
    const box = screen.getByRole("searchbox");
    fireEvent.change(box, { target: { value: "비트코" } });
    fireEvent.compositionStart(box);
    fireEvent.change(box, { target: { value: "비트코인" } });
    await screen.findByRole("option", { name: /비트코인/ });
    return { box, onSelect };
  }

  it("조합 중 엔터에서는 고르지 않고 칸도 그대로다", async () => {
    const { box, onSelect } = await composing();
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229, isComposing: true });
    expect(onSelect).not.toHaveBeenCalled();
    expect(box).toHaveValue("비트코인");
  });

  it("Safari 순서 — 조합 확정 뒤 오는 keyCode 229 엔터도 고르지 않는다", async () => {
    const { box, onSelect } = await composing();
    fireEvent.compositionEnd(box, { data: "인" });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 229, isComposing: false });
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("조합 중 방향키는 항목을 옮기지 않고, 확정 뒤 엔터가 맨 위를 고른다", async () => {
    const { box, onSelect } = await composing();
    fireEvent.keyDown(box, { key: "ArrowDown", keyCode: 229, isComposing: true });
    fireEvent.keyDown(box, { key: "ArrowDown", keyCode: 229, isComposing: true });
    fireEvent.compositionEnd(box, { data: "인" });
    fireEvent.keyDown(box, { key: "Enter", keyCode: 13 });
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith(BTC);
    expect(box).toHaveValue("");
  });
});

describe("목록 상태", () => {
  const statusText = () => screen.getByTestId("coin-list-status").textContent ?? "";

  it("받아 두었으면 기준 시각을 한국 시간으로 보인다", async () => {
    routeSearch(() => Promise.resolve(response([BTC])));
    await typeIn("btc");
    await screen.findByRole("option", { name: /비트코인/ });
    expect(statusText()).toContain("목록 기준 10-03 09:05");
  });

  it("결과가 없고 목록이 있으면 결과 없음이다", async () => {
    routeSearch(() => Promise.resolve(response([])));
    await typeIn("zzzz");
    expect(await screen.findByText("해당하는 코인을 찾지 못했습니다.")).toBeInTheDocument();
  });

  it("목록을 받은 적이 없으면 결과 없음이 아니라 처음 받는 중이다", async () => {
    routeSearch(() => Promise.resolve(response([], NEVER)));
    await typeIn("btc");
    await waitFor(() => expect(statusText()).toContain("코인 목록을 처음 받는 중입니다"));
    expect(screen.queryByText("해당하는 코인을 찾지 못했습니다.")).toBeNull();
  });

  it("새로 받는 중이면 이전 목록으로 찾는다고 알린다", async () => {
    routeSearch(() => Promise.resolve(response([BTC], REFRESHING)));
    await typeIn("btc");
    await waitFor(() => expect(statusText()).toContain("목록을 새로 받는 중"));
    expect(statusText()).toContain("이전 목록으로 찾습니다");
  });

  it("갱신이 실패했으면 사유와 이전 목록의 기준 시각이다", async () => {
    const failed: CoinListStatus = { ...READY, state: "failed", reason: "blocked" };
    routeSearch(() => Promise.resolve(response([BTC], failed)));
    await typeIn("btc");
    await waitFor(() => expect(statusText()).toContain("시세 출처가 접근을 막았습니다"));
    expect(statusText()).toContain("이전 목록 기준 10-03 09:05");
  });

  it("목록 없이 실패했으면 받지 못했다고 알린다 — 결과 없음이 아니다", async () => {
    const failed: CoinListStatus = { ...NEVER, state: "failed", reason: "network" };
    routeSearch(() => Promise.resolve(response([], failed)));
    await typeIn("btc");
    await waitFor(() => expect(statusText()).toContain("코인 목록을 받지 못했습니다"));
    expect(statusText()).toContain("출처에 연결하지 못했습니다");
    expect(screen.queryByText("해당하는 코인을 찾지 못했습니다.")).toBeNull();
  });

  it("한글 이름만 받지 못했으면 영문으로 찾는다고 알린다", async () => {
    const list: CoinListStatus = {
      ...READY, koreanNames: { state: "failed", asOf: AS_OF, reason: "network" } };
    routeSearch(() => Promise.resolve(response([BTC], list)));
    await typeIn("btc");
    await waitFor(() => expect(statusText()).toContain("한글 이름을 새로 받지 못했습니다"));
  });
});

describe("목록 갱신 진행 (FR-005b)", () => {
  it("처음 받는 중이면 구독해 받은 쪽 수를 실시간으로 보인다", async () => {
    routeSearch(() => Promise.resolve(response([], NEVER)));
    await typeIn("btc");
    await waitFor(() => expect(subscription.calls).toBe(1));
    act(() => subscription.handlers?.onSnapshot(
      { edition: "en", pagesDone: 12, pagesExpected: null, coinsSeen: 1200 }));
    expect(screen.getByTestId("coin-list-status").textContent).toContain("영문 12쪽 받음");
  });

  it("다시 받는 중이면 전체 쪽 수 어림과 함께 보인다", async () => {
    routeSearch(() => Promise.resolve(response([BTC], REFRESHING)));
    await typeIn("btc");
    await waitFor(() => expect(subscription.calls).toBe(1));
    act(() => subscription.handlers?.onSnapshot(
      { edition: "ko", pagesDone: 8, pagesExpected: 37, coinsSeen: 800 }));
    expect(screen.getByTestId("coin-list-status").textContent).toContain("한국어 8/37쪽");
  });

  it("끝나면 검색을 다시 보낸다", async () => {
    const get = routeSearch(() => Promise.resolve(response([], NEVER)));
    await typeIn("btc");
    await waitFor(() => expect(subscription.calls).toBe(1));
    const before = get.mock.calls.length;
    get.mockImplementation((() => Promise.resolve(response([BTC]))) as never);
    act(() => subscription.handlers?.onCompleted());
    expect(await screen.findByRole("option", { name: /비트코인/ })).toBeInTheDocument();
    expect(get.mock.calls.length).toBe(before + 1);
  });

  it("실패를 받으면 사유를 보인다", async () => {
    routeSearch(() => Promise.resolve(response([], NEVER)));
    await typeIn("btc");
    await waitFor(() => expect(subscription.calls).toBe(1));
    act(() => subscription.handlers?.onFailed("blocked", "403"));
    expect(screen.getByTestId("coin-list-status").textContent).toContain(
      "시세 출처가 접근을 막았습니다");
  });

  it("목록이 준비되어 있으면 구독하지 않는다", async () => {
    routeSearch(() => Promise.resolve(response([BTC])));
    await typeIn("btc");
    await screen.findByRole("option", { name: /비트코인/ });
    expect(subscription.calls).toBe(0);
  });

  it("화면을 떠나면 구독을 끊는다", async () => {
    routeSearch(() => Promise.resolve(response([], NEVER)));
    const { view } = await typeIn("btc");
    await waitFor(() => expect(subscription.calls).toBe(1));
    view.unmount();
    expect(subscription.unsubscribe).toHaveBeenCalled();
  });
});
