/**
 * 커서 가까이 상자의 누적 납입 원금·적금 금리 (011 T007) — FR-015, FR-032, research R11-12, ui-wireframes §5.
 *
 * - 점에 `principal`이 있으면 잔고 다음 줄이 "누적 납입 원금"이다(표와 같은 `formatMoneyWithSymbol`)
 * - 적금 시계열(`priceKind "installment_rate"`)은 잔고·누적 납입 원금·수익률·적금 금리·정기예금 금리 순이다. 정기예금 금리가 없는
 *   달은 "—"다(0이 아니다)
 * - 키가 없으면 기존 줄 목록과 같다(`chartHover.test.ts` 그대로)
 */
import { describe, expect, it } from "vitest";
import { hoverView } from "@/lib/chartHover";
import { formatAnnualRate } from "@/lib/format";
import type { SimulationPoint, SimulationSeriesResponse } from "@/lib/types";

const series = (points: SimulationPoint[], over: Partial<SimulationSeriesResponse> = {}): SimulationSeriesResponse => ({
  from: points[0].date, to: points[points.length - 1].date, principalCurrency: "KRW", basisCurrency: "KRW",
  downsampled: false, algorithm: "lttb", sourcePointCount: points.length, points, gaps: [], provisionalFrom: null,
  ...over,
});

describe("누적 납입 원금 줄", () => {
  it("적립식 주식은 주가·잔고·누적 납입 원금·수익률 순이다", () => {
    const view = hoverView(series([
      { date: "2026-09-15", balance: "17232000", returnRate: "0.045112", principal: "16500000", price: "71800" },
    ], { priceKind: "stock_adjusted_close", priceCurrency: "KRW" }), "2026-09-15");
    expect(view?.lines.map((l) => l.label)).toEqual(["주가(수정 종가)", "잔고", "누적 납입 원금", "수익률"]);
    expect(view?.lines[2]).toEqual({ label: "누적 납입 원금", value: "₩16,500,000" });
  });

  it("가격이 없는 응답에서도 principal이 있으면 잔고 다음에 둔다", () => {
    const view = hoverView(series([
      { date: "2026-09-15", balance: "1000000", returnRate: "0.010000", principal: "990000" },
    ]), "2026-09-15");
    expect(view?.lines.map((l) => l.label)).toEqual(["잔고", "누적 납입 원금", "수익률"]);
  });

  it("principal 키가 없으면 지금 줄 목록이다", () => {
    const view = hoverView(series([
      { date: "2026-09-15", balance: "1000000", returnRate: "0.010000", price: "71800" },
    ], { priceKind: "stock_adjusted_close", priceCurrency: "KRW" }), "2026-09-15");
    expect(view?.lines.map((l) => l.label)).toEqual(["주가(수정 종가)", "잔고", "수익률"]);
  });
});

describe("적금 상자", () => {
  const INSTALLMENT = series([
    { date: "2026-01-15", balance: "141000000", returnRate: "0.031000", principal: "130000000", price: "3.1",
      depositRate: "2.9" },
    { date: "2026-02-01", balance: "142000000", returnRate: "0.032000", principal: "131000000", price: "3.2" },
    { date: "2026-10-01", balance: "150000000", returnRate: "0.040000", principal: "139000000", price: null,
      priceMissing: "unpublished" },
  ], { priceKind: "installment_rate", priceCurrency: null });

  it("잔고·누적 납입 원금·수익률·적금 금리·정기예금 금리 순이다", () => {
    const view = hoverView(INSTALLMENT, "2026-01-15");
    expect(view?.lines.map((l) => l.label)).toEqual(["잔고", "누적 납입 원금", "수익률", "적금 금리", "정기예금 금리"]);
    expect(view?.lines[3].value).toBe(`연 ${formatAnnualRate("3.1")}`);
    expect(view?.lines[4].value).toBe(`연 ${formatAnnualRate("2.9")}`);
  });

  it("그 달 정기예금 금리가 없으면 —이다", () => {
    expect(hoverView(INSTALLMENT, "2026-02-01")?.lines[4]).toEqual({ label: "정기예금 금리", value: "—" });
  });

  it("미발표 달의 적금 금리는 —와 미발표다", () => {
    expect(hoverView(INSTALLMENT, "2026-10-01")?.lines[3]).toEqual({ label: "적금 금리", value: "—", missing: "미발표" });
  });
});
