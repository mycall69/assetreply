/**
 * 부동산 월별 투자 성과 표 (T034) — 009 FR-017, FR-018, FR-020, FR-021, FR-026, FR-028, SC-006, SC-010, ui-wireframes E5.
 *
 * - 열 11개, 금액 열의 통화(KRW)는 머리글 아래 줄(008 D4와 같은 자리 — `span.block`)
 * - **적용 시세 칸은 두 줄** — 시세와 그 아래 "창·건수", 추정·잠정이면 글자로 덧붙인다(색만으로 전달하지 않는다, FR-017·FR-018)
 * - 그 달 평균은 거래가 없으면 "—", 시세 없음 달은 적용 시세 "시세 없음"·평가액·투자 수익·수익률 "—"(0이 아니다, FR-026)
 * - 취득 비용은 **매입 행에만** — 합계와 그 아래 취득세(지방교육세·농어촌특별세 포함 — 항목은 `title`)·중개 수수료(FR-020)
 * - 재산세는 7월·9월 "(1/2)"·"(2/2)", 7월 일괄이면 "(일괄)". 종부세는 12월만. 다른 달은 **빈칸** — 0을 채우면 "안 냄"과 구별할 수
 *   없다(FR-028). 계산하지 못한 해(`taxGaps`)의 7·9월 재산세·12월 종부세 칸은 "계산 불가"(FR-021)
 * - **세금의 기준 시세**(그해 6월)가 추정이면 "6월 시세 추정", 잠정이면 "6월 시세 잠정"을 세금 아래에 붙이고, 칸의 `title`에 기준 시세·
 *   창·건수("2025-06 시세 2,300,000,000 · 3개월·7건")를 넣는다(FR-021)
 * - 최신순, 표는 내용 폭(`w-max`) — 1440px에서 가로 스크롤이 없다(SC-010)
 *
 * ## 이 테스트가 전제하는 모듈 (T039가 따른다)
 *
 * `@/components/realestate/RealEstatePerformanceTable` — `export function RealEstatePerformanceTable({ rows, taxGaps })`
 * - `rows: RealEstateRow[]`(서버 순서 그대로 — 최신순), `taxGaps: number[]`(`summary.taxGaps`)
 * - 머리글 한 줄(`thead`의 `tr` 하나), 행마다 `td` 열한 칸. `title`은 그 칸(`td`)이나 칸 안의 요소에 둔다
 */
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RealEstatePerformanceTable } from "@/components/realestate/RealEstatePerformanceTable";
import { SIM_ROWS } from "./support/realEstateSimulationFixtures";

const COLUMNS = ["월", "거래", "그 달 평균", "적용 시세", "취득 비용", "재산세", "종부세", "누적 비용", "평가액", "투자 수익",
  "수익률"];
const COL = Object.fromEntries(COLUMNS.map((name, i) => [name, i])) as Record<string, number>;

const headers = () => screen.getAllByRole("columnheader");
/** 머리글의 이름 — 통화 줄(`span.block`)을 뺀 글자. */
const nameOf = (h: HTMLElement) =>
  (h.textContent ?? "").replace(h.querySelector("span.block")?.textContent ?? "\u0000", "").trim();
const bodyRows = () => screen.getAllByRole("row").slice(1);
/** 그 달 행의 칸들. */
function rowOf(month: string): HTMLElement[] {
  const found = bodyRows().find((r) => within(r).getAllByRole("cell")[0].textContent === month);
  if (found === undefined) throw new Error(`${month} 행이 없다`);
  return within(found).getAllByRole("cell");
}
const text = (month: string, column: string) => rowOf(month)[COL[column]].textContent ?? "";
/** 칸의 도움말 — 칸 자신이나 칸 안의 요소의 `title`. */
function titleOf(month: string, column: string): string {
  const td = rowOf(month)[COL[column]];
  return td.getAttribute("title") ?? td.querySelector("[title]")?.getAttribute("title") ?? "";
}

function renderTable(taxGaps: number[] = [2023]) {
  render(<RealEstatePerformanceTable rows={SIM_ROWS} taxGaps={taxGaps} />);
}

describe("열", () => {
  it("열 11개", () => {
    renderTable();
    expect(headers().map(nameOf)).toEqual(COLUMNS);
  });

  it("금액 열의 통화는 머리글 아래 줄이다", () => {
    renderTable();
    const units = headers().map((h) => h.querySelector("span.block")?.textContent ?? null);
    expect(units).toEqual([null, null, "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", "(KRW)", null]);
  });

  it("표는 내용 폭이다", () => {
    renderTable();
    expect(screen.getByRole("table").className).toContain("w-max");
  });
});

describe("행", () => {
  it("최신순이고 한 달에 한 줄", () => {
    renderTable();
    expect(bodyRows().map((r) => within(r).getAllByRole("cell")[0].textContent)).toEqual(SIM_ROWS.map((r) => r.month));
  });

  it("행마다 칸 11개", () => {
    renderTable();
    for (const r of bodyRows()) expect(within(r).getAllByRole("cell")).toHaveLength(11);
  });

  it("거래가 있는 달 — 원 단위 쉼표, 부호 있는 수익률", () => {
    renderTable();
    const cells = rowOf("2026-09").map((c) => c.textContent ?? "");
    expect(cells[COL["거래"]]).toBe("14");
    expect(cells[COL["그 달 평균"]]).toBe("2,441,428,571");
    expect(cells[COL["누적 비용"]]).toBe("117,401,400");
    expect(cells[COL["평가액"]]).toBe("2,441,428,571");
    expect(cells[COL["투자 수익"]]).toBe("300,860,504");
    expect(cells[COL["수익률"]]).toBe("+14.27%");
  });

  it("손실이면 음수 부호", () => {
    renderTable();
    expect(text("2021-03", "투자 수익")).toBe("-84,973,000");
    expect(text("2021-03", "수익률")).toBe("-4.20%");
  });

  it("그 달 거래가 없으면 그 달 평균은 — 다(0이 아니다)", () => {
    renderTable();
    expect(text("2026-10", "거래")).toBe("0");
    expect(text("2026-10", "그 달 평균")).toBe("—");
  });
});

describe("적용 시세 — 두 줄", () => {
  it("넓힌 창이면 시세 아래에 창·건수와 추정·잠정", () => {
    renderTable();
    const cell = rowOf("2026-10")[COL["적용 시세"]];
    expect(cell.textContent).toContain("2,450,000,000");
    expect(within(cell).getByText("3개월·41건 추정·잠정")).toBeInTheDocument();
  });

  it("그 달 거래로 정했고 잠정 달이면 잠정만", () => {
    renderTable();
    const cell = rowOf("2026-09")[COL["적용 시세"]];
    expect(cell.textContent).toContain("2,441,428,571");
    expect(within(cell).getByText("1개월·14건 잠정")).toBeInTheDocument();
  });

  it("확정 달의 그 달 시세면 창·건수만", () => {
    renderTable();
    const cell = rowOf("2021-03")[COL["적용 시세"]];
    expect(within(cell).getByText("1개월·6건")).toBeInTheDocument();
    expect(cell.textContent).not.toContain("추정");
    expect(cell.textContent).not.toContain("잠정");
  });

  it("시세 없음 달 — 적용 시세는 시세 없음, 평가액·투자 수익·수익률은 —", () => {
    renderTable();
    expect(text("2022-05", "적용 시세")).toBe("시세 없음");
    expect(text("2022-05", "평가액")).toBe("—");
    expect(text("2022-05", "투자 수익")).toBe("—");
    expect(text("2022-05", "수익률")).toBe("—");
    // 비용은 그대로 쌓여 있다.
    expect(text("2022-05", "누적 비용")).toBe("95,000,000");
  });
});

describe("취득 비용", () => {
  it("매입 행에만 — 합계와 그 아래 취득세·중개", () => {
    renderTable();
    const cost = text("2021-03", "취득 비용");
    expect(cost).toContain("84,973,000");
    // 취득세 = 취득세 60,695,000 + 지방교육세 6,069,500 + 농어촌특별세 0.
    expect(cost).toContain("취득세 66,764,500");
    expect(cost).toContain("중개 18,208,500");
  });

  it("취득세의 항목은 title로 밝힌다", () => {
    renderTable();
    const help = titleOf("2021-03", "취득 비용");
    expect(help).toContain("60,695,000");
    expect(help).toContain("지방교육세 6,069,500");
    expect(help).toContain("농어촌특별세 0");
  });

  it("다른 달은 빈칸이다", () => {
    renderTable();
    for (const month of ["2026-10", "2026-09", "2022-05"]) expect(text(month, "취득 비용")).toBe("");
  });
});

describe("보유세 — 낸 달에만", () => {
  it("재산세는 7월·9월에 나눠 낸 차례를 붙인다", () => {
    renderTable();
    expect(text("2026-07", "재산세")).toContain("3,104,390");
    expect(text("2026-07", "재산세")).toContain("(1/2)");
    expect(text("2026-09", "재산세")).toContain("3,104,390");
    expect(text("2026-09", "재산세")).toContain("(2/2)");
  });

  it("7월에 한 번에 냈으면 (일괄)", () => {
    renderTable();
    expect(text("2024-07", "재산세")).toContain("180,000");
    expect(text("2024-07", "재산세")).toContain("(일괄)");
  });

  it("종부세는 12월에만", () => {
    renderTable();
    expect(text("2025-12", "종부세")).toContain("1,234,560");
    expect(text("2025-12", "재산세")).toBe("");
    expect(text("2026-09", "종부세")).toBe("");
  });

  it("내지 않은 달은 0이 아니라 빈칸이다", () => {
    renderTable();
    for (const month of ["2026-10", "2022-05", "2021-03"]) {
      expect(text(month, "재산세")).toBe("");
      expect(text(month, "종부세")).toBe("");
    }
  });

  it("계산하지 못한 해는 7·9월 재산세와 12월 종부세가 계산 불가다", () => {
    renderTable([2023]);
    expect(text("2023-07", "재산세")).toBe("계산 불가");
    expect(text("2023-09", "재산세")).toBe("계산 불가");
    expect(text("2023-12", "종부세")).toBe("계산 불가");
    // 그 해라도 세금이 없는 칸은 빈칸이다.
    expect(text("2023-12", "재산세")).toBe("");
    expect(text("2023-07", "종부세")).toBe("");
  });

  it("계산 불가는 그 해에만이다", () => {
    renderTable([]);
    expect(text("2023-07", "재산세")).toBe("");
    expect(text("2023-12", "종부세")).toBe("");
  });
});

describe("세금의 기준 시세 (FR-021)", () => {
  it("그해 6월 시세가 추정이면 6월 시세 추정과 title의 기준 시세·창·건수", () => {
    renderTable();
    expect(text("2025-12", "종부세")).toContain("6월 시세 추정");
    expect(titleOf("2025-12", "종부세")).toContain("2025-06 시세 2,300,000,000 · 3개월·7건");
  });

  it("그해 6월 시세가 잠정이면 6월 시세 잠정", () => {
    renderTable();
    expect(text("2026-09", "재산세")).toContain("6월 시세 잠정");
    expect(text("2026-09", "재산세")).not.toContain("추정");
    expect(titleOf("2026-09", "재산세")).toContain("2026-06 시세 2,400,000,000 · 1개월·9건");
  });

  it("확정 실측이면 덧붙이지 않지만 title은 있다", () => {
    renderTable();
    expect(text("2024-07", "재산세")).not.toContain("6월 시세");
    expect(titleOf("2024-07", "재산세")).toContain("2024-06 시세 1,900,000,000 · 1개월·4건");
  });
});
