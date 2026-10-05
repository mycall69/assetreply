/**
 * 표와 최근 시뮬레이션 배치 (010 T032) — FR-015~FR-017, SC-004(구조), research R10-10, data-model 6절, ui-wireframes F3.
 *
 * **경계 폭을 상수로 두지 않는다** — 줄바꿈 flex의 기본 크기로 정해진다. 표 칸은 `flex: 999 1 auto`(기본 크기 = 표 고유 폭), 이력 칸은
 * `flex: 1 1 400px`. 두 칸의 기본 크기 합이 본문 폭을 넘으면 이력이 다음 줄(전체 폭)로 내려간다 — 줄을 나누는 것은 기본 크기라 나란히 둔
 * 표는 줄지 않는다. 표 칸의 `min-w-0`는 창이 표 하나도 담지 못할 때(1440px 미만) 지금처럼 **표 안에서** 가로 스크롤하게 둔다 — 없으면 표
 * 칸이 줄지 않아 화면 전체가 가로로 넘친다(구현 중 확인 — 표 부품이 `overflow-x-auto` 안에 있다). 고정 폭·미디어 쿼리는 없다.
 * 이력 칸은 sticky(표를 내려도 남는다)이고 안에서 세로 스크롤한다. 결과가 없으면 이력 칸만이다.
 *
 * 네 이력 부품의 행은 줄바꿈한다 — 400px 칸에서 버튼 묶음이 다음 줄로 내려가고 칸 안 가로 넘침이 없다.
 *
 * 실제 경계 폭·잘림은 jsdom에 배치가 없어 브라우저 확인(T036)이 잰다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { TableWithHistory } from "@/components/TableWithHistory";
import { CryptoHistory } from "@/components/crypto/CryptoHistory";
import { DepositHistory } from "@/components/deposit/DepositHistory";
import { RealEstateHistory } from "@/components/realestate/RealEstateHistory";
import { SimulationHistory } from "@/components/stock/SimulationHistory";

function draw(withTable = true) {
  render(<TableWithHistory
    table={withTable ? <section data-testid="the-table">표</section> : null}
    history={<section data-testid="the-history">이력</section>} />);
}

const slotOf = (testid: string) => screen.getByTestId(testid).parentElement as HTMLElement;

describe("TableWithHistory", () => {
  it("바깥은 줄바꿈 flex다", () => {
    draw();
    expect(screen.getByTestId("table-with-history")).toHaveClass("flex", "flex-wrap", "items-start", "gap-5");
  });

  it("표 칸은 기본 크기가 표 고유 폭이고 고정 폭이 없다", () => {
    draw();
    const table = slotOf("the-table");
    expect(table).toHaveClass("flex-[999_1_auto]", "min-w-0");
    expect([...table.classList].filter((c) => /^(max-)?w-/.test(c))).toEqual([]);
  });

  it("이력 칸은 400px 기본, sticky, 안에서 세로 스크롤", () => {
    draw();
    expect(slotOf("the-history")).toHaveClass(
      "flex-[1_1_400px]", "sticky", "top-4", "self-start", "max-h-[calc(100vh-2rem)]", "overflow-y-auto");
  });

  it("표 → 이력 순서이고 둘 다 같은 바깥 안에 있다", () => {
    draw();
    const outer = screen.getByTestId("table-with-history");
    const [first, second] = [...outer.children];
    expect(first).toBe(slotOf("the-table"));
    expect(second).toBe(slotOf("the-history"));
  });

  it("결과가 없으면 이력 칸만이다", () => {
    draw(false);
    const outer = screen.getByTestId("table-with-history");
    expect(outer.children).toHaveLength(1);
    expect(outer.children[0]).toBe(slotOf("the-history"));
  });
});

describe("네 이력 부품의 행은 줄바꿈한다", () => {
  const handlers = { onToggle: vi.fn(), onRemove: vi.fn(), onCompare: vi.fn(), onRerun: vi.fn() };
  const common = { selected: [] as string[], comparing: false, saveError: null, ...handlers };

  it.each([
    ["주식", () => render(<SimulationHistory {...common} entries={[{ id: "s", stock: { market: "KRX", symbol: "005930.KS",
      name: "삼성전자", currency: "KRW" }, start: "2021-08-01", principal: "86997", principalCurrency: "KRW", reinvest: false,
      savedAt: "2026-10-05T00:00:00Z" }]} />)],
    ["가상자산", () => render(<CryptoHistory {...common} entries={[{ id: "c", coin: { coinId: 1, symbol: "BTC", name: "Bitcoin",
      nameKo: "비트코인", slug: "bitcoin", currency: "USD" }, start: "2020-01-15", principal: "10000", principalCurrency: "USD",
      savedAt: "2026-10-04T00:00:00Z" }]} />)],
    ["예금", () => render(<DepositHistory {...common} entries={[{ id: "d", institution: "commercial_bank", start: "2020-01-15",
      principal: "10000000", savedAt: "2026-10-04T00:00:00Z" }]} />)],
    ["부동산", () => render(<RealEstateHistory {...common} entries={[{ id: "r", complexId: 12, complexName: "헬리오시티",
      umd: "1171010700", area: "30k", areaLabel: "30평대(국평)", buyDate: "2021-03-15", buyPrice: null,
      savedAt: "2026-10-05T00:00:00Z" }]} />)],
  ])("%s", (_name, draw) => {
    draw();
    expect(screen.getByTestId("history-row")).toHaveClass("flex-wrap");
  });
});
