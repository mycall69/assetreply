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

/** 표의 기간 단위 (004 FR-006). 기본값은 `daily`다 (FR-007). */
export type PeriodUnit = "daily" | "weekly" | "monthly";

/**
 * 기간 단위가 적용된 표 행 (004 contracts/rest-api.md).
 *
 * `periodFrom`~`periodTo`는 이 행이 덮는 구간이다. 선택 날짜가 어느 행에 속하는지
 * **화면이** 판정하려면 필요하다 — 기준일만으로는 알 수 없다 (FR-019, research R4-7).
 *
 * `shiftedFrom`은 **옮겨졌을 때만 키가 있다**(FR-014). 정상 상태에 값을 두면 화면이
 * 존재 여부가 아니라 내용을 검사해야 한다.
 *
 * `isOngoing`은 항상 명시된다 — "확인했고 아니다"와 "확인하지 않았다"가 구별되어야 한다.
 */
export interface PeriodRow extends DailyRow {
  periodFrom: string;
  periodTo: string;
  shiftedFrom?: string;
  isOngoing: boolean;
}

export interface DailyResponse {
  currency: CurrencyCode;
  period: PeriodUnit;
  quoteUnit: number;
  appliedSpread: DerivedRates;
  spreadBasis: "current";
  rows: PeriodRow[];
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

/* ───────────────────────── 005: 주식 투자 시뮬레이션 ───────────────────────── */

/** 거래 시장. 시세 출처의 식별 체계를 따른다. */
export type StockMarket = "KRX" | "NASDAQ" | "NYSE" | "AMEX" | "TSE";

/** 투자 원금으로 고를 수 있는 통화 (FR-003). */
export type PrincipalCurrency = "KRW" | "USD" | "JPY" | "EUR";

/**
 * 검색 결과 한 항목 (FR-002a).
 *
 * **시장과 통화를 함께 준다**(FR-002b). 같은 이름이 여러 시장에 있을 수 있고,
 * 통화가 다르면 환전 여부와 수익률 기준이 달라진다.
 */
export interface StockSearchResult {
  market: StockMarket;
  symbol: string;
  name: string;
  currency: string;
}

/** 표 행의 종류 (FR-025). 월 첫 거래일 스냅샷과 배당락일 둘뿐이다. */
export type SimulationRowKind = "month_first" | "dividend";

/**
 * 성과 표 한 행.
 *
 * `dividendPerShare`·`dividendYield`는 **배당락 행에만 있다**(FR-026). 월 행에 0을
 * 넣으면 "배당이 0원"과 "배당이 없음"을 구별할 수 없다.
 *
 * `fxRate`·`fxRateDate`는 외화 종목일 때만 있다. `fxRateDate`가 `date`와 다를 수
 * 있다 — 주식 거래일과 환율 고시일은 일치하지 않는다 (FR-041c).
 */
export interface SimulationRow {
  date: string;
  kind: SimulationRowKind;
  openPrice: DecimalString;
  dividendPerShare?: DecimalString;
  dividendYield?: DecimalString;
  boughtShares: number;
  heldShares: number;
  cash: DecimalString;
  principal: DecimalString;
  balance: DecimalString;
  profit: DecimalString;
  returnRate: DecimalString;
  fxRate?: DecimalString;
  fxRateDate?: string;
}

/**
 * 성과 요약 (FR-031).
 *
 * `asOf`는 계산이 **어느 날짜까지**인지다. 시세가 끊기면 오늘이 아니고 `isFinal`이
 * 거짓이 된다 (FR-014b). `isFinal`은 항상 명시된다 — "확인했고 아니다"와 "확인하지
 * 않았다"가 구별되어야 한다.
 */
export interface SimulationSummary {
  principal: DecimalString;
  profit: DecimalString;
  returnRate: DecimalString;
  asOf: string;
  isFinal: boolean;
}

/**
 * 시뮬레이션에 적용된 조건 (FR-018).
 *
 * 수수료율·세율을 함께 싣는 이유는 설정이 언제든 바뀌기 때문이다. 결과만 남으면
 * **어느 조건에서 나온 수치인지 알 수 없다.**
 */
export interface SimulationCondition {
  start: string;
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  tradeFeeRate: DecimalString;
  dividendTaxRate: DecimalString;
}

/**
 * 초기 환전 정보 (FR-019~022). 원금 통화와 종목 통화가 다를 때만 있다.
 *
 * **평가 환산과 다른 환율이다.** 초기 환전은 실제로 돈을 바꾸는 1회 행위라 현금 살 때
 * 환율에 우대가 붙고, 평가는 값어치를 재는 것이라 매매기준율을 쓴다 (FR-041b).
 */
export interface ExchangeInfo {
  rate: DecimalString;
  rateDate: string;
  kind: "cash_buy_discounted";
  spreadDiscount: DecimalString;
}

export interface SimulationResponse {
  stock: StockSearchResult;
  condition: SimulationCondition;
  summary: SimulationSummary;
  exchange?: ExchangeInfo;
  rows: SimulationRow[];
  hasMore: boolean;
  oldestReturned: string | null;
}

/** 수집 중 응답 (FR-047). 부분 결과를 200으로 내려보내지 않는다 (FR-049). */
export interface SimulationCollecting {
  status: "collecting";
  market: StockMarket;
  symbol: string;
  jobId: number;
  missingFrom: string;
  missingThrough: string;
  progressUrl: string;
}

/** 차트용 시계열 한 점. 금액·비율은 **원금 통화 기준**이다 (FR-041). */
export interface SimulationPoint {
  date: string;
  balance: DecimalString;
  returnRate: DecimalString;
}

export interface SimulationSeriesResponse {
  from: string;
  to: string;
  principalCurrency: PrincipalCurrency;
  downsampled: boolean;
  algorithm: string;
  sourcePointCount: number;
  points: SimulationPoint[];
  gaps: SeriesGap[];
}

/** 수수료·세율 (FR-015, FR-016). 통화별이 아니라 전역 하나다. */
export interface StockSettings {
  tradeFeeRate: DecimalString;
  dividendTaxRate: DecimalString;
  isDefault: boolean;
}

/**
 * 이력 한 항목 (FR-036). 종목명만 남기면 같은 종목의 다른 조건을 구분할 수 없다.
 *
 * **수익률은 들어 있지 않다.** 결과는 설정(수수료·세율)과 환율의 함수라 바뀌는데,
 * 저장해 두면 그 사실이 드러나지 않아 **조용히 낡은 값**이 목록에 남는다 (R5-9).
 * 지금의 수익률은 비교를 실행해 받은 시계열이 말한다.
 */
export interface SimulationHistoryEntry {
  id: string;
  stock: StockSearchResult;
  start: string;
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  savedAt: string;
}
