/**
 * 기준금리 응답 대역 (014 반복 2026-10-11d T205) — contracts A14~A16. 값은 T202 실측(2026-10-11 네이버 증권 기준금리)과 같다.
 */
import type {
  PolicyRateBankId, PolicyRateDecision, PolicyRateDetail, PolicyRateRow, PolicyRatesResponse, RateCommentaryResponse,
} from "@/lib/types";

const BASE: Record<PolicyRateBankId, PolicyRateRow> = {
  fed: {
    bank: "fed", name: "미국연방준비은행", flag: "🇺🇸", rateKind: "연방기금금리 목표 범위 상단",
    rate: "4.00", change: "0.25", direction: "up", decidedOn: "2026-09-17", announcedAt: "2026-09-16T18:00:00Z",
    nextMeetingOn: "2026-10-29", state: "ready", failure: null, lastSuccessAt: "2026-10-11T09:40:00Z",
  },
  bok: {
    bank: "bok", name: "한국은행", flag: "🇰🇷", rateKind: "기준금리",
    rate: "3.00", change: "0.25", direction: "up", decidedOn: "2026-08-27", announcedAt: "2026-08-27T01:00:00Z",
    nextMeetingOn: "2026-10-22", state: "ready", failure: null, lastSuccessAt: "2026-10-11T09:40:00Z",
  },
  ecb: {
    bank: "ecb", name: "유럽중앙은행", flag: "🇪🇺", rateKind: "주요 재융자 금리",
    rate: "2.65", change: "-0.25", direction: "down", decidedOn: "2026-09-10", announcedAt: "2026-09-10T12:15:00Z",
    nextMeetingOn: "2026-10-29", state: "ready", failure: null, lastSuccessAt: "2026-10-11T09:40:00Z",
  },
  boe: {
    bank: "boe", name: "영국은행", flag: "🇬🇧", rateKind: "Bank Rate",
    rate: "3.75", change: "0.00", direction: "flat", decidedOn: "2026-09-17", announcedAt: "2026-09-17T11:00:00Z",
    nextMeetingOn: "2026-11-05", state: "ready", failure: null, lastSuccessAt: "2026-10-11T09:40:00Z",
  },
  boj: {
    bank: "boj", name: "일본은행", flag: "🇯🇵", rateKind: "단기 정책금리",
    rate: "1.25", change: "0.25", direction: "up", decidedOn: "2026-09-18", announcedAt: "2026-09-18T02:54:04Z",
    nextMeetingOn: "2026-10-30", state: "ready", failure: null, lastSuccessAt: "2026-10-11T09:40:00Z",
  },
};

export const BANK_ORDER: PolicyRateBankId[] = ["fed", "bok", "ecb", "boe", "boj"];

export function rowOf(bank: PolicyRateBankId, over: Partial<PolicyRateRow> = {}): PolicyRateRow {
  return { ...BASE[bank], ...over };
}

export function ratesOf(over: Partial<Record<PolicyRateBankId, Partial<PolicyRateRow>>> = {}, refreshAfterSeconds = 60): PolicyRatesResponse {
  return {
    source: "네이버 증권",
    sourceUrl: "https://stock.naver.com/market/marketindex/bondAndInterest/standardInterest",
    refreshAfterSeconds,
    banks: BANK_ORDER.map((bank) => rowOf(bank, over[bank])),
  };
}

/** 받는 중인 행 — 결정이 아직 없다. */
export const COLLECTING: Partial<PolicyRateRow> = {
  rate: null, change: null, direction: null, decidedOn: null, announcedAt: null, nextMeetingOn: null,
  state: "collecting", lastSuccessAt: null,
};

/** 한국은행 결정 이력(최신부터) — 동결 포함, 저장된 첫 결정은 전회대비 없음. */
export const BOK_DECISIONS: PolicyRateDecision[] = [
  { decidedOn: "2026-08-27", announcedAt: "2026-08-27T01:00:00Z", rate: "3.00", change: "0.25", direction: "up" },
  { decidedOn: "2026-07-16", announcedAt: "2026-07-16T01:00:00Z", rate: "2.75", change: "0.25", direction: "up" },
  { decidedOn: "2026-05-28", announcedAt: "2026-05-28T01:00:00Z", rate: "2.50", change: "0.00", direction: "flat" },
  { decidedOn: "2025-10-23", announcedAt: "2025-10-23T01:00:00Z", rate: "2.50", change: "0.00", direction: "flat" },
  { decidedOn: "2025-05-29", announcedAt: null, rate: "2.50", change: "-0.25", direction: "down" },
  { decidedOn: "2020-05-28", announcedAt: null, rate: "2.75", change: "1.25", direction: "up" },
  { decidedOn: "2016-01-14", announcedAt: null, rate: "1.50", change: null, direction: null },
];

export function detailOf(over: Partial<PolicyRateDetail> = {}): PolicyRateDetail {
  return {
    ...rowOf("bok"),
    firstDecidedOn: "2016-01-14",
    lastDecidedOn: "2026-08-27",
    decisions: BOK_DECISIONS,
    ...over,
  };
}

export function rateCommentaryOf(over: Partial<RateCommentaryResponse> = {}): RateCommentaryResponse {
  return {
    bank: "bok",
    source: "네이버 증권",
    sourceUrl: "https://stock.naver.com/news",
    status: "ok",
    fetchedAt: "2026-10-11T09:40:00Z",
    decisionDate: "2026-08-27",
    items: [
      {
        title: "[속보]한은 금리 인상 결정에 찬물…7000피 탈환 다음으로", summary: "코스피 요약 원문", publisher: "이데일리",
        publishedAt: "2026-08-27T06:34:15Z", publishedText: null, url: "https://n.news.naver.com/mnews/article/018/0006100001",
      },
      {
        title: "한은 '연속 인상'에도…증권가 \"점도표 쇼크없다\" 안도", summary: null, publisher: "연합뉴스",
        publishedAt: "2026-08-27T05:48:22Z", publishedText: null, url: "https://n.news.naver.com/mnews/article/001/0015600002",
      },
    ],
    failure: null,
    ...over,
  };
}
