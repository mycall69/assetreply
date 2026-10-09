/**
 * 비교 표 (013 T019) — FR-011, FR-012, FR-013, FR-014, ui-wireframes F5.
 *
 * 값은 서버의 `comparison` 블록 문자열이다 — 표는 형식만 입히고 계산하지 않는다(헌법 원칙 VI). 비용은 합과 두 몫(반영·매도 가정)을
 * 보이고, "현재 가치 − 비용 − 투자 원금"이 투자 수익과 다른 까닭을 칸이 밝힌다(FR-011 실패 양상).
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { CompareTable, type CompareRow } from "@/components/compare/CompareTable";
import { ok, SAMSUNG_T, collectingStock } from "./support/compareFixtures";

const row = (key: string, name: string, over = {}, summary: Record<string, unknown> = {}): CompareRow => ({
  key, name, href: null,
  state: { status: "ok", data: { ...ok(SAMSUNG_T, over), summary } },
});

function renderTable(rows: CompareRow[], props: Partial<Parameters<typeof CompareTable>[0]> = {}) {
  return render(<CompareTable rows={rows} method="lump_sum" sort={null} onSort={vi.fn()} onRetry={vi.fn()} {...props} />);
}

const bodyRows = () => screen.getAllByRole("row").slice(1);

describe("열", () => {
  // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
  // 013 승인 2026-10-09 — 반복 2026-10-09b(투자 시뮬레이션 모달)로 줄 끝에 열이 하나 늘었다.
  it("열한 개의 열이다", () => {
    renderTable([row("a", "XLK")]);
    const heads = screen.getAllByRole("columnheader").map((h) => h.textContent ?? "");
    expect(heads.map((h) => h.replace(/[▲▼ⓘ]/g, "").trim())).toEqual(
      ["대상", "기준일", "투자 원금", "시작일 단가", "기준일 단가", "등락", "현재 가치", "비용", "투자 수익", "수익률", "투자 시뮬레이션"]);
  });

  it("값은 서버 문자열에 형식만 입힌다", () => {
    renderTable([row("a", "XLK")]);
    const cells = within(bodyRows()[0]).getAllByRole("cell");
    expect(cells[1].textContent).toContain("2026-10-06");
    expect(cells[2].textContent).toContain("₩20,000,000");
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    expect(cells[6].textContent).toContain("₩539,297,203");
    expect(cells[7].textContent).toContain("-₩113,030,970");
    expect(cells[8].textContent).toContain("₩409,114,677");
    // 013 승인 2026-10-09 — 반복 2026-10-09c(FR-021): 백분율의 정수부를 세 자리마다 쉼표로 끊는다.
    expect(cells[9].textContent).toContain("+2,045.57%");
  });
});

describe("투자 원금", () => {
  it("외화 원금은 입력 통화와 괄호의 원화다", () => {
    renderTable([row("a", "AAPL", { principal: { amount: "10000", currency: "USD", krw: "13581000" } })]);
    expect(within(bodyRows()[0]).getAllByRole("cell")[2].textContent).toContain("$10,000 (₩13,581,000)");
  });

  it("부동산은 투입 금액과 매입가 · 취득 비용 포함이다", () => {
    renderTable([row("a", "헬리오시티", { principal: { amount: "1560000000", currency: "KRW", krw: "1560000000" } },
      { buyPrice: "1500000000" })], { method: "hold" });
    const cell = within(bodyRows()[0]).getAllByRole("cell")[2];
    expect(cell.textContent).toContain("₩1,560,000,000");
    expect(cell.textContent).toContain("매입가 ₩1,500,000,000");
    expect(cell.textContent).toContain("취득 비용 포함");
  });
});

describe("비용", () => {
  it("합과 반영·매도 가정 두 몫이다", () => {
    renderTable([row("a", "XLK")]);
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    const cell = within(bodyRows()[0]).getAllByRole("cell")[7];
    expect(cell.textContent).toContain("반영 ₩2,848,444");
    expect(cell.textContent).toContain("매도 가정 ₩110,182,526");
  });

  it("펼치면 항목이 글자로 보인다", () => {
    renderTable([row("a", "XLK")]);
    fireEvent.click(screen.getByRole("button", { name: /XLK 비용 내역/ }));
    const details = screen.getByRole("list", { name: /XLK 비용 내역/ });
    expect(details.textContent).toContain("매수 수수료 ₩5,427");
    expect(details.textContent).toContain("배당 소득세 ₩2,843,017");
    expect(details.textContent).toContain("매도 수수료 ₩80,884");
    expect(details.textContent).toContain("양도소득세 ₩110,101,642");
  });

  it("부동산 취득 항목은 투자 원금에 포함이라고 밝힌다", () => {
    const costs = { total: "15", reflected: { total: "15", items: [
      { kind: "acquisition_tax", amount: "10", inPrincipal: true },
      { kind: "property_tax", amount: "5", inPrincipal: false }] }, sale: null };
    renderTable([row("a", "헬리오", { costs } as never)], { method: "hold" });
    fireEvent.click(screen.getByRole("button", { name: /헬리오 비용 내역/ }));
    expect(screen.getByRole("list", { name: /헬리오 비용 내역/ }).textContent).toContain("취득세 ₩10 (투자 원금에 포함)");
  });

  it("비운 항목은 값 없이 까닭을 보이고 합도 비운다 — 0으로 메우지 않는다", () => {
    const costs = { total: null, reflected: { total: "100", items: [{ kind: "buy_fee", amount: "100", inPrincipal: false }] },
      sale: { total: null, blank: "outside_rules", items: [
        { kind: "sale_fee", amount: "50", inPrincipal: false }, { kind: "crypto_tax", amount: null, inPrincipal: false }] } };
    renderTable([row("a", "BTC", { costs, mainBasis: "unavailable", profit: null, returnRate: null } as never)],
      { method: "recurring" });
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    const cell = within(bodyRows()[0]).getAllByRole("cell")[7];
    expect(cell.textContent).toContain("—");
    expect(cell.textContent).not.toContain("₩0");
    expect(cell.textContent).toContain("과세 시행일 뒤");
  });

  it("칸 도움말이 현재 가치 − 비용 − 투자 원금과 투자 수익이 다른 까닭을 밝힌다", () => {
    renderTable([row("a", "XLK")]);
    expect(screen.getByRole("note", { name: "비용 도움말" }).getAttribute("title"))
      .toMatch(/이미.*들어 있습니다.*투자 수익과 다릅니다/);
  });
});

describe("투자 수익·수익률의 기준", () => {
  it.each([
    ["after_sale", "매도 후"],
    ["holding", "보유 중"],
  ])("%s → %s", (basis, text) => {
    renderTable([row("a", "XLK", { mainBasis: basis as never })]);
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    expect(within(bodyRows()[0]).getAllByRole("cell")[8].textContent).toContain(text);
  });

  it("값이 없으면 —", () => {
    renderTable([row("a", "XLK", { mainBasis: "unavailable", profit: null, returnRate: null })]);
    const cells = within(bodyRows()[0]).getAllByRole("cell");
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    expect(cells[8].textContent).toContain("—");
    expect(cells[9].textContent).toContain("—");
  });
});

describe("잠정·환율 (원칙 V)", () => {
  it("잠정 입력을 쓴 대상은 기준일에 ⏳와 까닭이다", () => {
    renderTable([row("a", "시중은행", { provisional: ["unpublished_rate", "not_final"] })]);
    const cell = within(bodyRows()[0]).getAllByRole("cell")[1];
    expect(cell.textContent).toContain("⏳");
    expect(cell.textContent).toContain("미발표 달 금리");
    expect(cell.textContent).toContain("기준일이 계산 끝 전");
  });

  it("외화 대상은 환율의 날짜와 출처를 보인다", () => {
    renderTable([row("a", "XLK", { fx: { currency: "USD", valuationRate: "1358.500000", valuationRateDate: "2026-10-06",
      source: "ECOS:731Y001", exchange: null } })]);
    const cell = within(bodyRows()[0]).getAllByRole("cell")[0];
    expect(cell.textContent).toContain("USD");
    expect(cell.textContent).toContain("1,358.50");
    expect(cell.textContent).toContain("2026-10-06");
    expect(cell.textContent).toContain("ECOS 매매기준율");
  });
});

describe("정렬", () => {
  const rows = [
    row("a", "가", { returnRate: "9.99" }),
    row("b", "나", { returnRate: "10" }),
    row("c", "다", { returnRate: null, mainBasis: "unavailable", profit: null }),
    row("d", "라", { returnRate: "-0.5" }),
  ];
  const names = () => bodyRows().map((r) => within(r).getAllByRole("cell")[0].textContent?.split(" ")[0]);

  it("처음 차례는 더한 차례다", () => {
    renderTable(rows);
    expect(names()).toEqual(["가", "나", "다", "라"]);
  });

  it("수 차례로 정렬하고 값이 없는 줄은 끝이다", () => {
    renderTable(rows, { sort: { key: "returnRate", direction: "desc" } });
    expect(names()).toEqual(["나", "가", "라", "다"]);
    expect(screen.getByRole("columnheader", { name: /수익률/ })).toHaveAttribute("aria-sort", "descending");
  });

  it("열 머리를 누르면 알린다", () => {
    const onSort = vi.fn();
    renderTable(rows, { onSort });
    fireEvent.click(screen.getByRole("button", { name: /투자 수익/ }));
    expect(onSort).toHaveBeenCalledWith("profit");
  });
});

describe("수집 중·실패", () => {
  const pending: CompareRow = { key: "h", name: "SK하이닉스", href: null,
    state: { status: "collecting", body: collectingStock(41), progress: { done: 100, total: 400 }, repeats: 1 } };
  const failed: CompareRow = { key: "f", name: "NAVER", href: null, state: { status: "failed", reason: "출처에 연결하지 못했습니다" } };

  it("맨 아래이고 값 칸은 비어 있다 — 0이 아니다", () => {
    renderTable([pending, row("a", "XLK"), failed], { sort: { key: "returnRate", direction: "asc" } });
    const all = bodyRows();
    expect(within(all[0]).getAllByRole("cell")[0].textContent).toContain("XLK");
    const cells = within(all[1]).getAllByRole("cell");
    // 013 승인 2026-10-09 — 반복(단가 등락)으로 투자 원금 뒤에 열이 셋 늘어 칸 번호가 3씩 밀렸다.
    // 013 승인 2026-10-09 — 반복 2026-10-09b(투자 시뮬레이션 모달)로 줄 끝에 열이 하나 늘었다.
    expect(cells.slice(1).map((c) => c.textContent)).toEqual(["", "", "", "", "", "", "", "", "", ""]);
  });

  it("수집 중은 받는 구간과 진행이다", () => {
    renderTable([pending]);
    expect(screen.getByText(/수집 중 · 2001-01-01 ~ 2020-01-31 받는 중/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "25");
  });

  it("실패는 까닭과 다시 시도다", () => {
    const onRetry = vi.fn();
    renderTable([failed], { onRetry });
    expect(screen.getByText(/수집 실패 — 출처에 연결하지 못했습니다/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "NAVER 다시 시도" }));
    expect(onRetry).toHaveBeenCalledWith("f");
  });

  it("막힘·수집 중·수집 실패의 글자가 서로 다르다(FR-014)", () => {
    renderTable([pending, failed]);
    expect(screen.getByText(/수집 중 ·/)).toBeInTheDocument();
    expect(screen.getByText(/수집 실패 —/)).toBeInTheDocument();
  });
});
