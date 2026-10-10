/**
 * 지표 모달의 일자별 표 (014 반복 2026-10-10b T108) — FR-013, FR-014, FR-029, SC-012, contracts D7.
 *
 * - 칸 일곱: 날짜·시가·고가·저가·종가·대비·등락률. 서버 문자열에 형식만 입힌다(원칙 VI). 값이 없으면 "—"
 * - 날짜 칸의 표시: 📅 옮김(`shiftedFrom`), ⏳ 끝나지 않은 구간(`isOngoing`), ⏳ 잠정(`provisional`)
 * - 결측 구간 행, 환율 머리 "고시 — 하루 한 값", 단위 단추 일·주·월
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IndicatorTable } from "@/components/dashboard/IndicatorTable";
import { rowOf, tableOf } from "./support/indicatorModalFixtures";

describe("칸", () => {
  it("일곱 칸이고 값에 형식을 입힌다", () => {
    render(<IndicatorTable table={tableOf()} period="daily" onPeriod={() => undefined} onMore={() => undefined} loading={false} />);
    const headers = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(headers).toEqual(["날짜", "시가", "고가", "저가", "종가", "대비", "등락률"]);
    const rows = screen.getAllByTestId("table-row");
    const second = within(rows[1]).getAllByRole("cell").map((c) => c.textContent);
    expect(second).toEqual(["10-08", "7,790.12", "7,812.50", "7,701.33", "7,801.25", "▼ 36.41", "-0.46%"]);
  });

  it("오늘 잠정 행은 ⏳이고 빈 칸은 —다", () => {
    render(<IndicatorTable table={tableOf()} period="daily" onPeriod={() => undefined} onMore={() => undefined} loading={false} />);
    const first = within(screen.getAllByTestId("table-row")[0]).getAllByRole("cell").map((c) => c.textContent);
    expect(first[0]).toContain("⏳ 잠정");
    expect(first.slice(1, 4)).toEqual(["—", "—", "—"]);
    expect(first[5]).toBe("▲ 34.64");
  });

  it("옮김·끝나지 않은 구간·결측 행", () => {
    const table = tableOf({
      period: "weekly",
      rows: [
        rowOf("2026-10-09", { isOngoing: true }),
        rowOf("2026-10-01", { shiftedFrom: "2026-10-02" }),
        { kind: "missing", date: "2001-09-11", dateTo: "2001-09-14" },
      ],
    });
    render(<IndicatorTable table={table} period="weekly" onPeriod={() => undefined} onMore={() => undefined} loading={false} />);
    const rows = screen.getAllByTestId("table-row");
    expect(rows[0]).toHaveTextContent("⏳ 끝나지 않은 구간");
    expect(rows[1]).toHaveTextContent("📅 옮김");
    expect(screen.getByText("결측 — 2001-09-11 ~ 2001-09-14 출처에 값 없음")).toBeInTheDocument();
  });

  it("환율은 고시임을 밝힌다", () => {
    render(<IndicatorTable table={tableOf({ seriesNote: "fx_fixing" })} period="daily" onPeriod={() => undefined} onMore={() => undefined} loading={false} />);
    expect(screen.getByText("고시 — 하루 한 값")).toBeInTheDocument();
  });

  it("해가 다른 날은 연도를 붙인다", () => {
    render(<IndicatorTable table={tableOf({ rows: [rowOf("2026-10-09"), rowOf("2025-12-31")] })} period="daily" onPeriod={() => undefined} onMore={() => undefined} loading={false} />);
    const dates = screen.getAllByTestId("table-row").map((r) => within(r).getAllByRole("cell")[0].textContent);
    expect(dates).toEqual(["10-09", "2025-12-31"]);
  });
});

describe("단위", () => {
  it("일·주·월 단추", () => {
    const onPeriod = vi.fn();
    render(<IndicatorTable table={tableOf()} period="daily" onPeriod={onPeriod} onMore={() => undefined} loading={false} />);
    const group = screen.getByRole("group", { name: "표 단위" });
    expect(within(group).getAllByRole("button").map((b) => b.textContent)).toEqual(["일", "주", "월"]);
    expect(within(group).getByRole("button", { name: "일" })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(within(group).getByRole("button", { name: "주" }));
    expect(onPeriod).toHaveBeenCalledWith("weekly");
  });
});
