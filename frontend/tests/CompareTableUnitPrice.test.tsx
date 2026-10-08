/**
 * 비교 표의 단가 등락 (013 반복 2026-10-09 T088) — FR-011, FR-011a, FR-012, ui-wireframes F5, data-model 3.2.
 *
 * 투자 원금과 현재 가치 사이에 시작일 단가·기준일 단가·등락. 값은 서버의 `comparison.unitPrice` 문자열이다 — 표는 형식만 입힌다(원칙 VI).
 * 주식은 상장국 통화의 수정주가("분할 반영"), 가상자산은 시세 통화의 시가(유효 숫자), 예금은 금리와 %p(등락률 "—"), 부동산은 시세다.
 * 값이 없으면 "—"와 까닭이다(원칙 V). "등락" 머리는 등락률(예금은 %p)로 정렬한다.
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CompareTable, type CompareRow } from "@/components/compare/CompareTable";
import type { UnitPrice } from "@/lib/types";
import { BTC_T, SAMSUNG_T, ok } from "./support/compareFixtures";

const point = (date: string, value: string | null, over: Partial<UnitPrice["asOf"]> = {}) => ({
  date, value, provisional: false, estimated: false, missing: null, ...over,
});

const SAMSUNG: UnitPrice = {
  kind: "share", basis: "split_restated_close", currency: "KRW",
  start: point("2010-01-04", "16180.000000"), asOf: point("2026-10-07", "55000.000000"),
  change: "38820.000000", changeRate: "2.399258", split: { ratio: "50:1" },
};
const XLK: UnitPrice = {
  kind: "share", basis: "split_restated_close", currency: "USD",
  start: point("2010-01-04", "20.830000"), asOf: point("2026-10-07", "289.100000"),
  change: "268.270000", changeRate: "12.878060", split: null,
};
const DOWN: UnitPrice = {
  kind: "share", basis: "split_restated_close", currency: "JPY",
  start: point("2021-08-02", "2100.000000"), asOf: point("2026-10-07", "1890.000000"),
  change: "-210.000000", changeRate: "-0.100000", split: null,
};
const SHIB: UnitPrice = {
  kind: "coin", basis: "daily_open", currency: "USD",
  start: point("2021-11-01", "0.0000530"), asOf: point("2026-10-03", "0.0000123"),
  change: "-0.0000407", changeRate: "-0.767924", split: null,
};
const BANK: UnitPrice = {
  kind: "rate", basis: "published_rate", currency: null,
  start: point("2015-01-01", "2.100000"), asOf: point("2026-08-01", "2.450000", { provisional: true }),
  change: "0.350000", changeRate: null, split: null,
};
const HOME: UnitPrice = {
  kind: "home", basis: "market_price", currency: "KRW",
  start: point("2021-03-01", "2100000000", { estimated: true }), asOf: point("2026-10-01", null, { missing: "no_trades" }),
  change: null, changeRate: null, split: null,
};

const row = (key: string, name: string, unitPrice: UnitPrice | null, target: unknown = SAMSUNG_T): CompareRow => ({
  key, name, href: null, state: { status: "ok", data: ok(target, { unitPrice }) },
});

function renderTable(rows: CompareRow[], props: Partial<Parameters<typeof CompareTable>[0]> = {}) {
  return render(<CompareTable rows={rows} method="lump_sum" sort={null} onSort={vi.fn()} onRetry={vi.fn()} {...props} />);
}

const cellOf = (name: string, testId: string) =>
  within(screen.getAllByRole("row").find((r) => r.textContent?.includes(name)) as HTMLElement).getByTestId(testId);

describe("열", () => {
  it("투자 원금과 현재 가치 사이에 단가 열 셋이다", () => {
    renderTable([row("a", "삼성전자", SAMSUNG)]);
    const heads = screen.getAllByRole("columnheader").map((h) => (h.textContent ?? "").replace(/[▲▼ⓘ]/g, "").trim());
    expect(heads).toEqual(["대상", "기준일", "투자 원금", "시작일 단가", "기준일 단가", "등락", "현재 가치", "비용", "투자 수익", "수익률"]);
  });

  it("등락 칸 도움말은 수익률과 다른 까닭을 말한다", () => {
    renderTable([row("a", "삼성전자", SAMSUNG)]);
    const help = screen.getByRole("note", { name: "등락 도움말" });
    expect(help.getAttribute("title")).toBe(
      "단가 등락은 1단위 가격만의 변화입니다 — 배당·수수료·세금·환율·적립 시점이 빠져 수익률과 다릅니다. 주식은 수정주가(분할 반영)입니다");
  });
});

describe("주식", () => {
  it("상장국 통화의 수정주가와 날짜, 분할 반영 표식", () => {
    renderTable([row("a", "삼성전자", SAMSUNG)]);
    const start = cellOf("삼성전자", "unit-start");
    expect(start).toHaveTextContent("₩16,180");
    expect(start).toHaveTextContent("2010-01-04");
    expect(start).toHaveTextContent("분할 반영 50:1");
    const asOf = cellOf("삼성전자", "unit-asof");
    expect(asOf).toHaveTextContent("₩55,000");
    expect(asOf).toHaveTextContent("2026-10-07");
    expect(asOf).not.toHaveTextContent("분할");
  });

  it("오르면 ▲ 빨강과 등락률, 내리면 ▼ 파랑", () => {
    renderTable([row("a", "삼성전자", SAMSUNG), row("b", "Toyota", DOWN)]);
    const up = cellOf("삼성전자", "unit-change");
    expect(up).toHaveTextContent("▲ ₩38,820");
    expect(up).toHaveTextContent("+239.92%");
    expect(up.className).toContain("text-red-700");
    const down = cellOf("Toyota", "unit-change");
    expect(down).toHaveTextContent("▼ ¥210");
    expect(down).toHaveTextContent("-10.00%");
    expect(down.className).toContain("text-blue-700");
  });

  it("해외 종목은 달러다(원화로 바꾸지 않는다)", () => {
    renderTable([row("a", "XLK", XLK)]);
    expect(cellOf("XLK", "unit-start")).toHaveTextContent("$20.83");
    expect(cellOf("XLK", "unit-asof")).toHaveTextContent("$289.10");
    expect(cellOf("XLK", "unit-change")).toHaveTextContent("▲ $268.27");
  });
});

describe("가상자산·예금·부동산", () => {
  it("가상자산은 유효 숫자를 잃지 않는다", () => {
    renderTable([row("a", "시바이누", SHIB, BTC_T)]);
    expect(cellOf("시바이누", "unit-start")).toHaveTextContent("$0.000053");
    expect(cellOf("시바이누", "unit-asof")).toHaveTextContent("$0.0000123");
    expect(cellOf("시바이누", "unit-change")).toHaveTextContent("▼ $0.0000407");
    expect(cellOf("시바이누", "unit-change")).toHaveTextContent("-76.79%");
  });

  it("예금은 금리와 달, 차이는 %p이고 등락률은 —, 미발표 달은 ⏳", () => {
    renderTable([row("a", "시중은행", BANK)]);
    const start = cellOf("시중은행", "unit-start");
    expect(start).toHaveTextContent("2.10%");
    expect(start).toHaveTextContent("2015-01");
    expect(start).not.toHaveTextContent("2015-01-01");
    const asOf = cellOf("시중은행", "unit-asof");
    expect(asOf).toHaveTextContent("2.45%");
    expect(asOf).toHaveTextContent("2026-08");
    expect(asOf).toHaveTextContent("⏳ 잠정");
    const change = cellOf("시중은행", "unit-change");
    expect(change).toHaveTextContent("▲ 0.35%p");
    expect(change).toHaveTextContent("—");
  });

  it("부동산 시세가 없으면 —와 까닭이고 등락을 비운다, 추정 시세는 ⏳", () => {
    renderTable([row("a", "헬리오시티아파트 30평대", HOME)]);
    expect(cellOf("헬리오시티", "unit-start")).toHaveTextContent("₩2,100,000,000");
    expect(cellOf("헬리오시티", "unit-start")).toHaveTextContent("⏳ 추정");
    const asOf = cellOf("헬리오시티", "unit-asof");
    expect(asOf).toHaveTextContent("—");
    expect(asOf).toHaveTextContent("시세 없음");
    expect(cellOf("헬리오시티", "unit-change").textContent).toBe("—");
  });

  it("단가가 없는 블록은 세 칸 모두 —다", () => {
    renderTable([row("a", "삼성전자", null)]);
    for (const id of ["unit-start", "unit-asof", "unit-change"]) expect(cellOf("삼성전자", id).textContent).toBe("—");
  });
});

describe("줄바꿈", () => {
  // T093 실측 — 열이 열 개가 되자 1440px 창에서 날짜가 "2026-10-"/"08"로, 등락의 ▲와 금액이 서로 다른 줄로 갈렸다.
  it("단가·등락 칸과 기준일 날짜는 줄을 바꾸지 않는다", () => {
    renderTable([row("a", "삼성전자", SAMSUNG)]);
    for (const id of ["unit-start", "unit-asof", "unit-change"]) expect(cellOf("삼성전자", id).className).toContain("whitespace-nowrap");
    const asOf = within(screen.getAllByRole("row")[1]).getAllByRole("cell")[1];
    expect(within(asOf).getByText("2026-10-06").className).toContain("whitespace-nowrap");
  });
});

describe("정렬", () => {
  const names = () => screen.getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[0].textContent);

  it("등락 머리는 등락률을 문자열 소수로 견준다 — 값 없는 줄은 끝", () => {
    const onSort = vi.fn();
    const rows = [row("a", "가", { ...SAMSUNG, changeRate: "0.9" }), row("b", "나", HOME),
      row("c", "다", { ...SAMSUNG, changeRate: "10.5" }), row("d", "라", DOWN)];
    const { rerender } = renderTable(rows, { onSort });
    fireEvent.click(screen.getByRole("button", { name: /^등락/ }));
    expect(onSort).toHaveBeenCalledWith("unitChange");
    rerender(<CompareTable rows={rows} method="lump_sum" sort={{ key: "unitChange", direction: "desc" }} onSort={onSort} onRetry={vi.fn()} />);
    expect(names()).toEqual(["다", "가", "라", "나"]);
  });

  it("예금은 %p 차이로 견준다", () => {
    const rows = [row("a", "가", { ...BANK, change: "-0.2" }), row("b", "나", { ...BANK, change: "0.35" })];
    renderTable(rows, { sort: { key: "unitChange", direction: "desc" } });
    expect(names()).toEqual(["나", "가"]);
  });
});
