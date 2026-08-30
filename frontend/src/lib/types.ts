/** 백엔드 응답 타입 (contracts/rest-api.md). 금액은 문자열로 유지한다. */

import type { CurrencyCode, DecimalString } from "./apiClient";

export type { CurrencyCode, DecimalString };

export interface DerivedRates {
  cashBuy: DecimalString;
  cashSell: DecimalString;
  remitSend: DecimalString;
  remitReceive: DecimalString;
}

export interface RateQuoted {
  status: "quoted";
  currency: CurrencyCode;
  date: string;
  quoteUnit: number;
  baseRate: DecimalString;
  derived: DerivedRates;
  appliedSpread: DerivedRates;
  /** "current" — 현재 스프레드를 과거 날짜에 적용한 가정 비교 (FR-026a) */
  spreadBasis: string;
  source: string;
}

/** 스프레드 설정 한 통화분 (contracts/rest-api.md). */
export interface SpreadRow extends DerivedRates {
  currency: CurrencyCode;
}

export interface RateReference {
  kind: "previous_business_day";
  date: string;
  quoteUnit: number;
  baseRate: DecimalString;
  note: string;
}

export interface RateNoQuote {
  status: "no_quote";
  currency: CurrencyCode;
  date: string;
  message: string;
  reference: RateReference | null;
}

export interface RateCollecting {
  status: "collecting";
  currency: CurrencyCode;
  date: string;
  jobId: number;
  missingDays: number;
}

export type RateResponse = RateQuoted | RateNoQuote | RateCollecting;

export interface CoverageRow {
  currency: CurrencyCode;
  coveredFrom: string;
  coveredThrough: string;
  firstAvailableDate: string | null;
  lastUpdatedAt: string;
}


/** 시계열 한 점 (contracts/rest-api.md `GET /api/fx/series`). */
export interface SeriesPoint {
  date: string;
  baseRate: DecimalString;
}

/** 결측 구간. `reason`이 고시 없음과 미수집을 구분한다 (FR-032). */
export interface SeriesGap {
  from: string;
  to: string;
  reason: "no_quote" | "not_collected";
}

export interface SeriesResponse {
  currency: CurrencyCode;
  quoteUnit: number;
  from: string;
  to: string;
  downsampled: boolean;
  algorithm: string;
  sourcePointCount: number;
  points: SeriesPoint[];
  gaps: SeriesGap[];
}

export interface SeriesCollecting {
  status: "collecting";
  currency: CurrencyCode;
  from: string;
  to: string;
  missingDays: number;
}


/** 진행률 스트림 상태 (contracts/sse-progress.md). */
export interface ProgressState {
  jobId: number;
  currency: CurrencyCode;
  status: "running" | "succeeded" | "partial" | "failed";
  chunksTotal: number;
  chunksDone: number;
  currentRange?: { from: string; to: string } | null;
  coveredThrough: string | null;
  lastError: string | null;
}

/** 수집 작업 이력 한 건 (contracts/rest-api.md `GET /api/fx/jobs`). */
export interface JobRow {
  jobId: number;
  currency: CurrencyCode;
  status: "running" | "succeeded" | "partial" | "failed";
  rangeStart: string;
  rangeEnd: string;
  chunksTotal: number;
  chunksDone: number;
  startedAt: string;
  finishedAt: string | null;
  lastError: string | null;
}
