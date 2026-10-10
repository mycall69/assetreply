/**
 * 코인 검색 결과 줄의 첫 일봉 (014 반복 2026-10-10f T160) — FR-033, contracts D12.
 *
 * 출처가 상장일을 주지 않는다 — 수집으로 알게 된 첫 일봉(`firstAvailableDate`)을 `첫 일봉 …`으로 밝힌다(거래소 상장일이 아니다).
 * 모르면 그 글자를 뺀다. 줄의 다른 칸은 그대로다.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CoinSearch } from "@/components/crypto/CoinSearch";
import { BTC, BTS, response, routeSearch } from "./support/coinSearchFixtures";

vi.mock("@/lib/cryptoListProgressStream", () => ({ subscribeCoinListProgress: () => () => undefined }));

beforeEach(() => {
  vi.restoreAllMocks();
});

async function options() {
  routeSearch(() => Promise.resolve(response([BTC, BTS])));
  render(<CoinSearch value={null} onSelect={vi.fn()} />);
  await userEvent.type(screen.getByRole("searchbox"), "b");
  return screen.findAllByRole("option");
}

describe("코인 검색 결과 줄의 첫 일봉", () => {
  it("아는 코인은 첫 일봉 …", async () => {
    const [btc] = await options();
    expect(btc.textContent).toContain("첫 일봉 2010-07-18");
    expect(btc.textContent).toContain("BTC · USD");
  });

  it("모르는 코인은 그 글자를 뺀다", async () => {
    const [, bts] = await options();
    expect(bts.textContent).not.toContain("첫 일봉");
    expect(bts.textContent).toContain("BTS · USD");
  });

  it("거래소 상장일이 아님을 마우스를 올리면 밝힌다", async () => {
    await options();
    expect(screen.getByTitle(/첫 일봉 — 거래소 상장일이 아닙니다/)).toBeInTheDocument();
  });
});
