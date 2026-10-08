/**
 * 막힘 판정과 시작일 제안 (013 T031) — FR-010, FR-013, FR-014, SC-003, research R13-6.
 *
 * 대상마다의 응답을 갈래로 나누고 비교 전체의 상태를 정한다. **막힌 대상이 하나라도 있으면 비교 전체를 막는다**(명확화 1) — 계산할 수
 * 없는 대상을 조용히 빼면 그 대상이 진 것으로 읽힌다. 시작일로 풀리는 대상들의 날짜 가운데 가장 늦은 날을 제안하되, **수집 중인 대상이
 * 남아 있으면 제안하지 않는다** — 수집이 끝나야 시작 가능 날짜를 아는 대상(시작 월의 일봉으로 판정하는 주식)이 있다.
 *
 * 날짜의 견주기는 `YYYY-MM-DD` 글자 차례다 — 금액 계산이 아니다.
 */
import { ApiError } from "./apiClient";
import type { CompareCollecting, ComparisonResponse } from "./types";

/** `start` 시작일을 옮기면 풀린다, `remove` 그 대상을 빼야 한다, `too_late` 시작일이 계산 끝보다 늦다. */
export type BlockKind = "start" | "remove" | "too_late";

export interface BlockReason {
  kind: BlockKind;
  code: string;
  /** 까닭 — "상장 전 — 2021-11-29부터" */
  text: string;
  /** 할 일 — "이 대상을 빼세요" */
  action: string;
  /** 갈래의 날짜(시작 가능 날짜·마지막 날·달). 없으면 `null`. */
  date: string | null;
}

export type TargetState =
  | { status: "requesting" }
  | { status: "ok"; data: ComparisonResponse }
  | { status: "collecting"; body: CompareCollecting; progress: { done: number; total: number } | null; repeats: number }
  | { status: "blocked"; reason: BlockReason }
  | { status: "failed"; reason: string };

export type Overall = "blocked" | "partial" | "complete";

const text = (body: Record<string, unknown> | null, key: string): string | null => {
  const value = body?.[key];
  return typeof value === "string" ? value : null;
};

const REMOVE = "이 대상을 빼세요";

function block(kind: BlockKind, code: string, reason: string, date: string | null, action: string): { blocked: BlockReason } {
  return { blocked: { kind, code, text: reason, action, date } };
}

/** 오류 → 막힘 또는 실패. 출처 오류·네트워크는 막힘이 아니라 그 대상의 실패다(다시 시도). */
export function classify(err: unknown): { blocked: BlockReason } | { failed: string } {
  if (!(err instanceof ApiError)) return { failed: "응답을 받지 못했습니다. 다시 시도하세요." };
  const body = err.body;
  const from = (key: string) => text(body, key);
  switch (err.code) {
    case "before_listing": {
      const date = from("startableFrom");
      const what = from("basis") === "price_start" ? "시세 시작 전" : "상장 전";
      return block("start", err.code, `${what} — ${date}부터`, date, "시작일을 옮기세요");
    }
    case "before_first_month": {
      const date = from("startableFrom");
      return block("start", err.code, `금리 시작 전 — ${date}부터`, date, "시작일을 옮기세요");
    }
    case "before_first_trade": {
      const date = from("startableFrom");
      const what = from("basis") === "tax_rules" ? "세법 표 시작 전" : "첫 거래 전";
      return block("start", err.code, `${what} — ${date}부터`, date, "매입일을 옮기세요");
    }
    case "fx_not_available_before": {
      const date = from("availableFrom");
      return block("start", err.code, `${from("currency") ?? ""} 환율 시작 전 — ${date}부터`.trim(), date, "시작일을 옮기세요");
    }
    case "start_after_end": {
      const date = from("lastDay");
      return block("too_late", err.code, `시작일이 계산 끝보다 늦습니다`, date, `시작일을 ${date} 이전으로 바꾸세요`);
    }
    case "installment_not_available":
      return block("remove", err.code, "정기 적금이 없는 투자처", null, REMOVE);
    case "unknown_coin":
      return block("remove", err.code, "목록에 없는 코인", null, REMOVE);
    case "unknown_stock":
      return block("remove", err.code, "알 수 없는 종목", null, REMOVE);
    case "unknown_complex":
      return block("remove", err.code, "알 수 없는 단지", null, REMOVE);
    case "region_retired":
      return block("remove", err.code, "없어진 시·군·구", null, REMOVE);
    case "no_trades_in_area":
      return block("remove", err.code, "그 평형의 거래가 없습니다", null, REMOVE);
    case "no_price_at_purchase": {
      const month = from("month");
      return block("remove", err.code, `그 달 시세 없음 (${month})`, month, "매입일을 바꾸거나 이 대상을 빼세요");
    }
    case "tax_rule_not_covered":
      return block("remove", err.code, "세법 표가 덮지 않는 날짜입니다", null, REMOVE);
    case "rate_missing": {
      const month = from("month");
      return block("remove", err.code, `금리가 없는 달 (${month})`, month, REMOVE);
    }
    case "no_price_data":
      return block("remove", err.code, "시세가 없습니다", null, REMOVE);
    case "price_symbol_unknown":
      return block("remove", err.code, "시세 출처가 모르는 종목입니다", null, REMOVE);
    case "no_rate_data":
      return block("remove", err.code, "금리가 없습니다", null, REMOVE);
    case "currency_pair_not_allowed":
    case "currency_not_allowed":
      return block("remove", err.code, "고를 수 없는 원금 통화입니다", null, "원금 통화를 바꾸거나 이 대상을 빼세요");
    default:
      return { failed: err.message || "계산에 실패했습니다. 다시 시도하세요." };
  }
}

/** 비교 전체 — 막힌 대상이 하나라도 있으면 막힘, 아니면 끝나지 않은 대상이 있으면 일부, 모두 끝나면 완료. */
export function overall(states: readonly TargetState[]): Overall {
  if (states.some((s) => s.status === "blocked")) return "blocked";
  return states.every((s) => s.status === "ok") ? "complete" : "partial";
}

/** 제안 날짜 — 시작일로 풀리는 날짜 가운데 가장 늦은 날. 수집 중인 대상이 있으면 `null`과 그 수다. */
export function suggestion(states: readonly TargetState[]): { date: string | null; collecting: number } {
  const collecting = states.filter((s) => s.status === "collecting" || s.status === "requesting").length;
  const dates = states.flatMap((s) => (s.status === "blocked" && s.reason.kind === "start" && s.reason.date !== null
    ? [s.reason.date] : []));
  if (collecting > 0 || dates.length === 0) return { date: null, collecting };
  return { date: dates.reduce((a, b) => (a > b ? a : b)), collecting: 0 };
}
