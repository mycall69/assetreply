/**
 * 가격 선의 구간 (010 T011, 반복 1 T043) — FR-003, SC-002, research R10-7, data-model 4절.
 *
 * - `priceSegments(points, gaps)` — 잔고와 **같은 자리**(`splitSeriesAtGaps` — 미수집·출처 결측·시세 없음)에서 끊고, **가격이 `null`인 점에서
 *   다시 끊는다**(예금 미발표·결측 달, 부동산 거래 없는 달). 휴장(`no_quote`)은 잇는다. `null` 점을 앞뒤 구간에 넣지 않는다 — 직전 값을
 *   복사하거나 앞뒤를 이으면 없는 가격이 있는 것처럼 보인다(헌법 원칙 V). 점 하나뿐인 구간도 남긴다(화면이 점으로 그린다)
 * - (반복 1) 분할 표식(`splitMarks`)은 없앴다 — 주가 선이 수정 종가라 분할 날 꺾이지 않는다(spec FR-008)
 */
import { describe, expect, it } from "vitest";
import { priceSegments } from "@/lib/chartSeries";
import type { SeriesGap } from "@/lib/types";

type P = { date: string; price?: string | null };
const p = (date: string, price: string | null = "1"): P => ({ date, price });
const dates = (segments: P[][]) => segments.map((s) => s.map((x) => x.date));

describe("priceSegments", () => {
  it("가격이 null인 점에서 끊고 그 점을 어느 구간에도 넣지 않는다", () => {
    const points = [p("2026-06-01"), p("2026-07-01"), p("2026-08-01", null), p("2026-09-01"), p("2026-10-01")];
    expect(dates(priceSegments(points, []))).toEqual([["2026-06-01", "2026-07-01"], ["2026-09-01", "2026-10-01"]]);
  });

  it("잔고와 같은 자리에서도 끊는다 — 출처 결측·시세 없음·미수집", () => {
    for (const reason of ["source_missing", "no_price", "not_collected"] as const) {
      const gap: SeriesGap = { from: "2021-03-01", to: "2021-03-02", reason };
      const points = [p("2021-02-27"), p("2021-02-28"), p("2021-03-03"), p("2021-03-04")];
      expect(dates(priceSegments(points, [gap]))).toEqual([["2021-02-27", "2021-02-28"], ["2021-03-03", "2021-03-04"]]);
    }
  });

  it("휴장(no_quote)은 잇는다", () => {
    const gap: SeriesGap = { from: "2021-08-07", to: "2021-08-08", reason: "no_quote" };
    const points = [p("2021-08-06"), p("2021-08-09")];
    expect(dates(priceSegments(points, [gap]))).toEqual([["2021-08-06", "2021-08-09"]]);
  });

  it("점 하나뿐인 구간도 남긴다 — 부동산의 앞뒤 달에 거래가 없는 달", () => {
    const points = [p("2021-04-01", null), p("2021-05-01"), p("2021-06-01", null), p("2021-07-01"), p("2021-08-01")];
    expect(dates(priceSegments(points, []))).toEqual([["2021-05-01"], ["2021-07-01", "2021-08-01"]]);
  });

  it("모든 점이 null이면 구간이 없다", () => {
    expect(priceSegments([p("2026-09-01", null), p("2026-10-01", null)], [])).toEqual([]);
  });

  it("가격 키가 없는 점(가격 없는 응답)은 그리지 않는다", () => {
    expect(priceSegments([{ date: "2021-01-01" }, { date: "2021-02-01" }], [])).toEqual([]);
  });
});
