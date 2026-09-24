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
  /**
   * 오늘이 지났는데도 잠정으로 남은 레코드 (FR-043a). 값이 있을 때만 존재한다.
   * 확정 전환이 일어나지 않았다는 뜻이며, 해당 통화의 증분 수집으로 해소된다.
   */
  staleProvisional?: { date: string };
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


// ── 003: 수집 실행·관측 ────────────────────────────────────────────

/** 진행 중 작업의 표시 상태 (contracts/rest-api 2절).
 *
 * 세 값으로 나누는 이유는 FR-006a가 "회수를 기다리는 중"을 요구하기 때문이다.
 * 두 값으로 합치면 사용자가 **기다려야 하는지 아닌지**를 알 수 없다. */
export type JobDisplayState = "running" | "stalled" | "awaiting_reclaim";

export interface ActiveJob {
  jobId: number;
  /** 이어받기 지점 (FR-011). 작업이 어디서부터 시작했는지가 곧 그 값이다. */
  rangeStart: string;
  chunksTotal: number;
  chunksDone: number;
  currentChunk: { from: string; to: string } | null;
  state: JobDisplayState;
}

export interface TimelineSnapshot {
  generatedAt: string;
  /** 참고 지표다. 한도 판정은 출처 응답으로만 한다 (research R3-5). */
  callsToday: number;
  currency: CurrencyCode;
  targetFrom: string;
  targetTo: string;
  coveredFrom: string | null;
  coveredThrough: string | null;
  /** **다른** 통화가 수집 중이면 그 코드. 없으면 null (FR-029). */
  busyWith: CurrencyCode | null;
  /** 진행 중일 때만 존재한다. 정상 상태에 빈 객체를 두지 않는다. */
  activeJob?: ActiveJob;
}

export type CollectionEventKind =
  | "job_started"
  | "chunk_requested"
  | "chunk_stored"
  /** 출처가 값을 주지 않은 구간(휴일 등). `chunk_failed`와 **반드시 구별한다** —
   *  합치면 시계열 공백의 원인을 되짚을 수 없다 (FR-021). */
  | "chunk_empty"
  | "chunk_failed"
  | "retry"
  | "rate_limited"
  | "job_finished"
  | "log_sink_failed";

export interface CollectionEventRow {
  jobId: number;
  currency: CurrencyCode;
  kind: CollectionEventKind;
  chunkFrom: string | null;
  chunkTo: string | null;
  rowsStored: number | null;
  detail: string | null;
  occurredAt: string;
}

export interface EventsResponse {
  events: CollectionEventRow[];
  /** 화면이 "왜 오래된 게 없는지"를 설명할 수 있게 한다 (FR-023). */
  retention: { jobsKept: number };
  /** 0보다 크면 이 기록은 불완전하다 (FR-018b). */
  eventsDropped: number;
}
