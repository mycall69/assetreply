/**
 * 막힘 판정과 시작일 제안 (013 T014) — FR-010, FR-013, FR-014, SC-003, research R13-6.
 *
 * 대상 하나라도 계산할 수 없으면 **비교 전체를 막는다**(명확화 1). 시작일로 풀리는 대상들의 날짜 가운데 가장 늦은 날을 제안하되,
 * **수집 중인 대상이 남아 있으면 제안하지 않는다** — 그 대상이 수집을 마친 뒤 제안한 날짜에서 다시 막힐 수 있다.
 */
import { describe, expect, it } from "vitest";
import { ApiError } from "@/lib/apiClient";
import { classify, overall, suggestion, type TargetState } from "@/lib/compareBlock";

const err = (status: number, code: string, body: Record<string, unknown> = {}) =>
  new ApiError(status, code, `${code} 메시지`, { status: code, message: `${code} 메시지`, ...body });

describe("classify", () => {
  it.each([
    [err(400, "before_listing", { startableFrom: "2015-03-02", basis: "listing" }), "start", "2015-03-02", "상장 전"],
    [err(400, "before_listing", { startableFrom: "2015-03-02", basis: "price_start" }), "start", "2015-03-02", "시세 시작 전"],
    [err(409, "before_first_month", { startableFrom: "2012-01-01" }), "start", "2012-01-01", "금리 시작 전"],
    [err(409, "before_first_trade", { startableFrom: "2020-02-01", basis: "first_trade" }), "start", "2020-02-01", "첫 거래 전"],
    [err(409, "fx_not_available_before", { availableFrom: "1990-01-02", currency: "USD" }), "start", "1990-01-02", "환율"],
    [err(400, "installment_not_available"), "remove", null, "정기 적금이 없는 투자처"],
    [err(404, "unknown_coin"), "remove", null, "목록에 없는 코인"],
    [err(404, "unknown_stock"), "remove", null, "알 수 없는 종목"],
    [err(400, "unknown_complex"), "remove", null, "알 수 없는 단지"],
    [err(409, "region_retired", { lawdCd: "11710" }), "remove", null, "시·군·구"],
    [err(409, "no_trades_in_area"), "remove", null, "거래가 없"],
    [err(409, "no_price_at_purchase", { month: "2010-01" }), "remove", "2010-01", "그 달 시세 없음"],
    [err(409, "tax_rule_not_covered", { tax: "acquisition", date: "2031-01-01" }), "remove", null, "세법"],
    [err(409, "rate_missing", { month: "2023-01" }), "remove", "2023-01", "금리"],
    [err(404, "no_price_data"), "remove", null, "시세"],
    [err(404, "price_symbol_unknown"), "remove", null, "시세"],
    [err(404, "no_rate_data"), "remove", null, "금리"],
    [err(400, "currency_pair_not_allowed", { allowed: ["KRW"] }), "remove", null, "통화"],
    [err(400, "currency_not_allowed", { allowed: ["KRW"] }), "remove", null, "통화"],
    [err(400, "start_after_end", { lastDay: "2026-10-07" }), "too_late", "2026-10-07", "2026-10-07 이전"],
  ])("%o → %s", (error, kind, date, text) => {
    const result = classify(error);
    expect("blocked" in result).toBe(true);
    if (!("blocked" in result)) return;
    expect(result.blocked.kind).toBe(kind);
    expect(result.blocked.date).toBe(date);
    expect(`${result.blocked.text} ${result.blocked.action}`).toContain(text);
  });

  it("시작일로 안 풀리는 사유는 빼라고 알린다", () => {
    const result = classify(err(400, "installment_not_available"));
    expect("blocked" in result && result.blocked.action).toContain("빼세요");
  });

  it("그 달 시세 없음은 매입일을 바꾸라고도 알린다", () => {
    const result = classify(err(409, "no_price_at_purchase", { month: "2010-01" }));
    expect("blocked" in result && result.blocked.action).toContain("매입일");
  });

  it.each([
    [err(502, "source_unavailable")],
    [err(503, "source_rate_limited")],
    [err(409, "fx_unavailable")],
    [err(500, "unknown")],
    [new TypeError("Failed to fetch")],
  ])("출처 오류·네트워크는 막힘이 아니라 실패다 — %o", (error) => {
    expect("failed" in classify(error)).toBe(true);
  });
});

const ok = (): TargetState => ({ status: "ok", data: {} as never });
const collecting = (): TargetState => ({ status: "collecting", body: { status: "collecting" } as never, progress: null, repeats: 1 });
const blocked = (kind: "start" | "remove" | "too_late", date: string | null): TargetState => ({
  status: "blocked", reason: { kind, code: "x", text: "까닭", action: "", date },
});

describe("overall", () => {
  it("막힌 대상이 하나라도 있으면 막힘이다", () => {
    expect(overall([ok(), blocked("remove", null), collecting()])).toBe("blocked");
  });

  it("막힘이 없고 끝나지 않은 대상이 있으면 일부다 — 실패도 막힘이 아니다", () => {
    expect(overall([ok(), collecting()])).toBe("partial");
    expect(overall([ok(), { status: "failed", reason: "출처 오류" }])).toBe("partial");
    expect(overall([ok(), { status: "requesting" }])).toBe("partial");
  });

  it("모두 끝났으면 완료다", () => {
    expect(overall([ok(), ok()])).toBe("complete");
  });

  it("수집 중이던 대상이 막힘으로 바뀌면(늦게 드러난 막힘) 막힘이다", () => {
    const before = [ok(), collecting()];
    expect(overall(before)).toBe("partial");
    expect(overall([before[0], blocked("start", "2016-01-04")])).toBe("blocked");
  });
});

describe("suggestion", () => {
  it("시작일로 풀리는 날짜 가운데 가장 늦은 날이다", () => {
    expect(suggestion([blocked("start", "2015-03-02"), blocked("start", "2016-01-04"), ok()]))
      .toEqual({ date: "2016-01-04", collecting: 0 });
  });

  it("수집 중인 대상이 있으면 제안하지 않는다", () => {
    expect(suggestion([blocked("start", "2015-03-02"), collecting()])).toEqual({ date: null, collecting: 1 });
  });

  it("시작일로 풀리는 대상이 없으면 제안이 없다", () => {
    expect(suggestion([blocked("remove", null), blocked("too_late", "2026-10-07")])).toEqual({ date: null, collecting: 0 });
  });
});
