/**
 * 검색 결과와 고른 종목의 종목명(코드) (T112) — 006 FR-025, SC-019, ui-wireframes W2. 반복 2026-10-03.
 *
 * 이름이 같거나 비슷한 종목(우선주·클래스·다른 시장의 같은 이름)을 코드 없이 고르면, 사용자는 고른 뒤에도
 * 무엇을 골랐는지 확인할 수 없다. 코드는 이름 옆에 **한 번만** 쓴다.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { StockSearch } from "@/components/stock/StockSearch";
import type { LocalStockResult } from "@/lib/types";
import {
  SAMSUNG,
  SAMSUNG_PREF,
  TOYOTA,
  external,
  local,
  routeGet,
} from "./support/stockSearchFixtures";

const BRK_B: LocalStockResult = {
  ...SAMSUNG, listingId: 5001, country: "US", market: "NYSE", symbol: "BRK-B", code: "BRKb",
  name: "버크셔 해서웨이 B", nameEn: "BERKSHIRE HATHAWAY INC", currency: "USD",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

async function typeQuery(text: string) {
  render(<StockSearch value={null} onSelect={vi.fn()} />);
  await userEvent.type(screen.getByRole("searchbox"), text);
}

const count = (text: string, part: string) => text.split(part).length - 1;

describe("검색 결과", () => {
  it("국내 결과는 종목명(6자리 코드)이고 코드를 두 번 쓰지 않는다", async () => {
    routeGet({ local: () => Promise.resolve(local([SAMSUNG, SAMSUNG_PREF])) });
    await typeQuery("삼성");
    const options = await within(screen.getByRole("region", { name: "국내·미국" }))
      .findAllByRole("option");
    expect(options[0].textContent).toContain("삼성전자(005930)");
    expect(options[1].textContent).toContain("삼성전자우(005935)");
    expect(count(options[0].textContent ?? "", "005930")).toBe(1);
    // 시장·통화는 그대로 함께 보인다 (005 FR-002b).
    expect(options[0].textContent).toContain("KRX · KRW");
  });

  it("미국 결과는 키움 코드가 아니라 티커다", async () => {
    routeGet({ local: () => Promise.resolve(local([BRK_B])) });
    await typeQuery("버크셔");
    const option = await screen.findByRole("option", { name: /버크셔/ });
    expect(option.textContent).toContain("버크셔 해서웨이 B(BRK-B)");
    expect(option.textContent).not.toContain("BRKb");
  });

  it("일본 결과도 종목명(4자리 코드)이다", async () => {
    routeGet({ external: () => Promise.resolve(external([TOYOTA])) });
    await typeQuery("토요타");
    const option = await within(screen.getByRole("region", { name: "일본" }))
      .findByRole("option");
    expect(option.textContent).toContain("Toyota Motor Corporation(7203)");
  });
});

describe("고른 종목 표시", () => {
  it("칸 아래에 종목명(코드)와 시장·통화를 보인다", () => {
    render(<StockSearch
      value={{ market: "KRX", symbol: "005930.KS", name: "삼성전자", currency: "KRW" }}
      onSelect={vi.fn()} />);
    const shown = screen.getByText("삼성전자(005930)");
    expect(shown.closest("p")?.textContent).toContain("KRX · KRW");
  });
});
