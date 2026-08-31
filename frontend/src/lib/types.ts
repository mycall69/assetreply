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
  /** 현재 값이 기본값과 같은지 (FR-033). 서버가 판정해 내려준다. */
  isDefault?: boolean;
}

/** `GET /api/fx/spreads` 응답 — 기본값을 함께 담아 화면이 차이를 표시한다. */
export interface SpreadsResponse {
  spreads: SpreadRow[];
  defaults: SpreadRow[];
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
  /** 잠정값일 때만 포함된다. 확정 구간과 시각적으로 구분해야 한다 (FR-017a). */
  isProvisional?: boolean;
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

/** 요약 응답 (contracts/rest-api.md `GET /api/fx/latest`). */
export interface LatestChange {
  comparedTo: string;
  absolute: DecimalString;
  percent: DecimalString;
  direction: "up" | "down" | "flat";
}

export interface LatestResponse {
  currency: CurrencyCode;
  quotePair: string;
  date: string | null;
  baseRate: DecimalString | null;
  quoteUnit: number;
  isProvisional: boolean;
  fetchedAt: string | null;
  change: LatestChange | null;
  status?: "no_data";
  message?: string;
}

/** 일자별 상세 행. 파생 4종은 **서버가 Decimal로 산출한** 문자열이다 (research R2-5). */
export interface DailyRow {
  date: string;
  baseRate: DecimalString;
  isProvisional: boolean;
  derived: DerivedRates;
}

export interface DailyResponse {
  currency: CurrencyCode;
  quoteUnit: number;
  appliedSpread: DerivedRates;
  spreadBasis: "current";
  rows: DailyRow[];
  hasMore: boolean;
  oldestReturned: string | null;
}

/** 오늘 새로고침 응답 (contracts/rest-api.md). */
export interface TodayRefreshResponse {
  currency: CurrencyCode;
  status: "updated" | "no_quote_today";
  date: string;
  baseRate?: DecimalString;
  isProvisional?: boolean;
  fetchedAt: string;
  joinedExisting: boolean;
  message?: string;
}

/** 스프레드 복원 응답. 부분 실패해도 성공분을 되돌리지 않는다 (FR-031a). */
export interface RestoreResponse {
  restored: CurrencyCode[];
  failed: { currency: CurrencyCode; reason: string }[];
  spreads: SpreadRow[];
}
