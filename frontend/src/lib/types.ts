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
  /** `source_missing` — 가상자산(007)의 받은 구간 안 출처 결측. 휴장이 없어 끊는다(FR-023). */
  reason: "no_quote" | "not_collected" | "source_missing";
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

/* ─────────────────── 006: 검색용 목록·일본 외부 검색·등록 ─────────────────── */

/** 검색용 목록의 단위 (006 FR-015). 단위마다 기준 시각이 따로다. */
export type ListingUnit = "KOSPI" | "KOSDAQ" | "NYSE" | "NASDAQ" | "AMEX";

/** 단위의 화면 상태 (006 data-model 2절). */
export type ListingState =
  | "never" | "refreshing" | "ready" | "stale" | "failed" | "auth_blocked";

/** 목록을 받지 못한 사유 (contracts `lists[].reason`). */
export type ListingReason =
  | "auth_missing" | "auth_failed" | "rate_limit" | "network" | "invalid";

/** 사용자가 할 일 (006 FR-028a). */
export type ListingAction = "set_credentials" | "wait" | "retry_later";

export interface ListingUnitStatus {
  unit: ListingUnit;
  state: ListingState;
  /** 온전히 받은 마지막 시각(UTC ISO). 한 번도 받지 못했으면 `null`. */
  asOf: string | null;
  reason?: ListingReason;
  action?: ListingAction;
}

export type StockKind = "stock" | "etf" | "reit";

/**
 * 로컬 목록 검색 결과 한 줄 (006 contracts `GET /api/stocks/search`).
 *
 * `market`·`symbol`은 **005의 시세 식별자**다. `listedOn`은 시작 가능 날짜가 아니라
 * **하한**이다(FR-005a).
 */
export interface LocalStockResult {
  listingId: number;
  country: "KR" | "US";
  market: StockMarket;
  symbol: string;
  code: string;
  name: string;
  nameEn: string | null;
  currency: string;
  kind: StockKind;
  listedOn: string | null;
  /** `missing` — 목록에서 빠진 종목. 지우지 않고 표시한다(FR-019). */
  listingStatus: "listed" | "missing";
  match: "exact" | "prefix" | "contains";
}

export interface LocalSearchResponse {
  query: string;
  results: LocalStockResult[];
  /** 상한에서 잘렸는가 (FR-024). */
  truncated: boolean;
  /** 결과가 없어도 항상 온다 — "결과 없음"과 "목록 없음"을 가르는 근거(FR-028). */
  lists: ListingUnitStatus[];
}

/** 일본 외부 검색 결과 (006 contracts `GET /api/stocks/search/external`). */
export interface ExternalStockResult {
  market: StockMarket;
  symbol: string;
  name: string;
  currency: string;
  kind: StockKind;
}

export interface ExternalSearchResponse {
  query: string;
  results: ExternalStockResult[];
}

/**
 * 검색에서 고른 것. **종목 식별이 아니다** — 식별은 등록 응답이 정한다(FR-030b).
 * 미국 종목은 목록과 005의 거래소가 다를 수 있다(FR-030a).
 */
export type StockChoice =
  | { source: "listing"; listingId: number; preview: LocalStockResult }
  | { source: "external"; result: ExternalStockResult };

/** 등록 응답 (006 contracts `POST /api/stocks/selection`). */
export interface SelectionResponse {
  market: StockMarket;
  symbol: string;
  name: string;
  currency: string;
  listedOn: string | null;
}

/** 표 행의 종류 (FR-025). 월 첫 거래일 스냅샷과 배당락일 둘뿐이다. */
/** 006 FR-058 — `reinvest`는 배당락 뒤 2번째 거래일의 재투자 매수 행이다. */
export type SimulationRowKind = "month_first" | "dividend" | "reinvest";

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
  /** 배당락 행의 배당 소득세(종목 통화). 해당 없으면 키가 없다 — 006 FR-059, FR-066. */
  dividendTax?: DecimalString;
  /** 매수가 있는 행의 매매 수수료(종목 통화). 해당 없으면 키가 없다 — 006 FR-059, FR-066. */
  tradeFee?: DecimalString;
  /** 배당락 행의 배당금 총액 — 세전(보유 수 × 주당 배당금), 종목 통화. 006 FR-067. */
  dividendTotal?: DecimalString;
  /** 배당락 행의 세후 배당금 총액 — 예수금에 들어온 금액, 종목 통화. 006 FR-067. */
  dividendTotalNet?: DecimalString;
  /** 잔고의 KRW 평가(그 행의 매매기준율). 해외 종목에만 있다 — 006 FR-066. */
  balanceKrw?: DecimalString;
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
  /**
   * 원금의 KRW 값 — 원금 통화가 KRW가 아닐 때만 있다. 첫 매수일의 매매기준율로 평가한다(006 FR-068).
   * `profit`·`returnRate`는 원금 통화와 관계없이 KRW 기준이다.
   */
  principalKrw?: DecimalString;
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

/**
 * 환율 수집 상태 (006 contracts 5절). 003의 수집 표에서 온다.
 *
 * `waiting`은 **다른 통화의 수집 중**이라 시작하지 못했다는 뜻이다 — `busyWith`에 그 통화.
 */
export type FxCollectState = "queued" | "collecting" | "waiting";

export interface FxCollecting {
  currency: CurrencyCode;
  state: FxCollectState;
  busyWith: CurrencyCode | null;
  missingFrom: string;
  missingThrough: string;
}

/**
 * 수집 중 응답 (FR-047). 부분 결과를 200으로 내려보내지 않는다 (FR-049).
 *
 * 006 — 주식 시세가 다 있으면 `jobId`·`progressUrl`·`missingFrom`·`missingThrough`가 없고,
 * 환율이 비었으면 `fx`가 있다. 둘 다 비면 둘 다 있다 (FR-045).
 */
export interface SimulationCollecting {
  status: "collecting";
  market: StockMarket;
  symbol: string;
  jobId?: number;
  missingFrom?: string;
  missingThrough?: string;
  progressUrl?: string;
  fx?: FxCollecting;
}

/**
 * 시작일이 시작 가능 날짜보다 이르다 (006 contracts 2절, 400 `before_listing`).
 *
 * - `listing`: 목록의 상장일보다 이르다. 시세를 받기 전에 온다
 * - `price_start`: 시세가 그보다 늦게 시작한다. 시세를 받은 뒤에 온다
 *
 * **시작일을 몰래 옮기지 않는다** — 화면이 그 날짜로 옮기는 수단을 그린다.
 */
export interface BeforeListingBody {
  status: "before_listing";
  message: string;
  startableFrom: string;
  basis: "listing" | "price_start";
}

/**
 * 수집으로 채울 수 없는 구간 (006 FR-043a, 409). **두 사유를 섞지 않는다** — 설정 밖은
 * 설정을 바꾸면 풀리는데 "출처에 없음"으로 말하면 영영 불가능한 것으로 읽힌다.
 */
export interface FxNotAvailableBefore {
  status: "fx_not_available_before";
  reason: "before_first_quote" | "before_probe_start";
  message: string;
  currency: CurrencyCode;
  availableFrom: string;
}

/** 차트용 시계열 한 점. 금액·비율은 **KRW 기준**이다 (006 FR-068 — 005 FR-041을 대체). */
export interface SimulationPoint {
  date: string;
  balance: DecimalString;
  returnRate: DecimalString;
}

export interface SimulationSeriesResponse {
  from: string;
  to: string;
  /** 입력한 원금 통화. 기준 통화가 아니다. */
  principalCurrency: PrincipalCurrency;
  /** 잔고·수익률의 기준 통화 — 항상 KRW다(006 FR-068). 범례와 비교는 이것으로 기준을 말한다. */
  basisCurrency: PrincipalCurrency;
  downsampled: boolean;
  algorithm: string;
  sourcePointCount: number;
  points: SimulationPoint[];
  gaps: SeriesGap[];
  /**
   * 잠정 구간의 시작일(008 FR-036) — 예금만 싣는다. 그 날짜부터 연한 색으로 그린다. 주식·가상자산 응답에는 이 키가 없고
   * 화면은 없는 것을 `null`로 읽는다.
   */
  provisionalFrom?: string | null;
}

/** 수수료·세율 (FR-015, FR-016). 배당 소득세는 국내·해외 두 값이다(006 FR-055). */
export interface StockSettings {
  tradeFeeRate: DecimalString;
  dividendTaxRateDomestic: DecimalString;
  dividendTaxRateForeign: DecimalString;
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

// ─────────────────────────── 007: 가상자산 ───────────────────────────

/** 코인 목록의 판 상태 (007 contracts/rest-api `list.state`). */
export type CoinListState = "ready" | "refreshing" | "never" | "failed";
/** 목록 갱신 실패 사유. 진행 스트림의 `failed.reason`과 같다. */
export type CoinListReason = "blocked" | "format" | "network" | "shrunk";

export interface CoinEditionStatus {
  state: CoinListState;
  /** 그 판을 온전히 받아 교체한 마지막 시각(UTC). 없으면 받은 적이 없다. */
  asOf: string | null;
  reason?: CoinListReason;
}

/** 영문 판(목록)의 상태와 한국어 판(한글 이름)의 상태. 한국어 판이 실패해도 영문으로 찾는다(FR-006). */
export interface CoinListStatus extends CoinEditionStatus {
  koreanNames: CoinEditionStatus;
}

/**
 * 코인 검색 결과 한 줄 (007 FR-003, FR-004). **식별자는 `coinId`다** — 심볼은 유일하지 않다(MAX 5개).
 */
export interface CoinSearchResult {
  coinId: number;
  symbol: string;
  name: string;
  /** 한국어 판이 준 한글 이름. 없으면 `null`(FR-006). */
  nameKo: string | null;
  slug: string | null;
  /** 시세 통화. 출처의 목록은 모두 USD다. */
  currency: string;
  /** 시가총액 순위. 없으면 `null`. */
  rank: number | null;
  listStatus: "listed" | "missing";
  /** 수집으로 발견한 첫 일봉. 없으면 아직 모른다(research R7-10). */
  firstAvailableDate: string | null;
  match: "exact" | "prefix" | "contains";
}

export interface CoinSearchResponse {
  query: string;
  results: CoinSearchResult[];
  truncated: boolean;
  list: CoinListStatus;
}

/** 목록 갱신 진행 (FR-005b). 판이 바뀌면 `pagesDone`이 0부터 다시 센다. */
export interface CoinListProgress {
  /** 지금 받는 판. 요청이 들어가고 아직 시작하지 않았으면 `null`. */
  edition: "en" | "ko" | null;
  pagesDone: number;
  /** 이전 갱신의 코인 수로 어림한 전체 쪽 수. 처음이면 `null`. */
  pagesExpected: number | null;
  coinsSeen: number;
}

/** 수집 실패 종류 (007 FR-020). 할 일이 다르다 — 차단은 기다려도 풀리지 않고, 형식 변경은 고쳐야 하고, 네트워크는 다시 하면 된다. */
export type CryptoFailureKind = "blocked" | "format" | "network" | "empty";

/**
 * 가상자산 표 한 행 (007 contracts/rest-api). **매달 첫 일봉**뿐이다 — 배당 행이 없다(FR-038).
 *
 * 수량은 소수 8자리 문자열(FR-026), 시가는 출처 원값(14자리, FR-040). `tradeFee`는 매수 행에만, `firstDayMissing`은 그 달 1일
 * 일봉이 없어 다른 날이 행이 된 경우에만 있다(FR-030). 금액 열은 시세 통화, 투자 수익·수익율은 KRW 기준이다(FR-035).
 */
export interface CryptoRow {
  date: string;
  kind: "month_first";
  openPrice: DecimalString;
  boughtQuantity: DecimalString;
  heldQuantity: DecimalString;
  tradeFee?: DecimalString;
  cash: DecimalString;
  principal: DecimalString;
  balance: DecimalString;
  balanceKrw?: DecimalString;
  profit: DecimalString;
  returnRate: DecimalString;
  fxRate?: DecimalString;
  fxRateDate?: string;
  firstDayMissing?: string;
}

/** 요약. `boughtOn`은 실제 매수일 — 시작 월 1일이 결측이면 1일이 아니다(FR-030). */
export interface CryptoSummary extends SimulationSummary {
  boughtOn: string;
}

export interface CryptoCondition {
  start: string;
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
  tradeFeeRate: DecimalString;
}

export interface CryptoCoinRef {
  coinId: number;
  symbol: string;
  name: string;
  nameKo: string | null;
  currency: string;
}

export interface CryptoSimulationResponse {
  coin: CryptoCoinRef;
  condition: CryptoCondition;
  summary: CryptoSummary;
  exchange?: ExchangeInfo;
  rows: CryptoRow[];
  hasMore: boolean;
  oldestReturned: string | null;
}

/** 수집 중(202). 일봉이 다 있으면 `jobId` 등이 없고, 환율이 다 있으면 `fx`가 없다. 결과를 싣지 않는다(FR-013). */
export interface CryptoCollecting {
  status: "collecting";
  coinId: number;
  jobId?: number;
  missingFrom?: string;
  missingThrough?: string;
  progressUrl?: string;
  fx?: FxCollecting;
}

/** 가상자산 거래 수수료율 (FR-032). 주식 설정과 따로다. */
export interface CryptoSettings {
  tradeFeeRate: DecimalString;
  isDefault: boolean;
}

/** 고른 코인의 식별과 표시 — 검색 결과와 이력이 함께 맞는다. **식별은 `coinId`다**(심볼은 유일하지 않다, FR-004). */
export interface CoinRef {
  coinId: number;
  symbol: string;
  name: string;
  nameKo: string | null;
  slug: string | null;
  currency: string;
  rank?: number | null;
}

/**
 * 가상자산 이력 한 줄 (FR-045). **조건만** 담는다 — 결과는 일봉·설정·환율의 함수라 바뀐다(005 R5-9). 주식 이력과 따로 둔다.
 */
export interface CryptoHistoryEntry {
  id: string;
  coin: Omit<CoinRef, "rank">;
  start: string;
  principal: DecimalString;
  principalCurrency: PrincipalCurrency;
  savedAt: string;
}

/* ───────────────────────── 008: 예금 투자 시뮬레이션 ───────────────────────── */

/** 투자처 키 — 화면 순서(FR-003). 출처의 통계표·항목 코드는 화면에 오지 않는다(헌법 원칙 II). */
export type DepositInstitutionKey =
  | "commercial_bank" | "savings_bank" | "credit_union" | "mutual_finance" | "saemaul";

/** 투자처 목록의 한 줄. 받기 전에는 범위를 모른다 — `null`이다(research R8-12). */
export interface DepositInstitution {
  key: DepositInstitutionKey;
  name: string;
  description: string;
  firstMonth: string | null;
  latestMonth: string | null;
  checkedOn: string | null;
}

export interface DepositInstitutionsResponse {
  institutions: DepositInstitution[];
  source: string;
  basis: string;
}

/** 수집 실패 종류(FR-016). 할 일이 다르다(ui-wireframes D8). */
export type DepositFailureKind = "auth" | "rate_limited" | "format" | "network";

/** 행 구분 — 가입 · 매달 1일 · 만기 · 재예치(FR-033). */
export type DepositRowKind = "join" | "month" | "maturity" | "reinvest";

/** 표의 행. 금액은 원 단위 정수 문자열, 금리는 출처 문자열(`"3.2"`), `rateMonth`는 `YYYY-MM`(잠정이면 대신 쓴 달). */
export interface DepositRow {
  date: string;
  kind: DepositRowKind;
  rate: DecimalString;
  rateMonth: string;
  provisional: boolean;
  principal: DecimalString;
  interest: DecimalString;
  tax: DecimalString;
  afterTax: DecimalString;
  balance: DecimalString;
  profit: DecimalString;
  returnRate: DecimalString;
}

/** 끝난 회차. */
export interface DepositTerm {
  no: number;
  joinedOn: string;
  maturesOn: string;
  rate: DecimalString;
  rateMonth: string;
  provisional: boolean;
  principal: DecimalString;
  interest: DecimalString;
  tax: DecimalString;
  afterTax: DecimalString;
}

/** 계산 끝에 진행 중인 회차. */
export interface DepositCurrentTerm {
  joinedOn: string;
  maturesOn: string;
  rate: DecimalString;
  rateMonth: string;
  principal: DecimalString;
  provisional: boolean;
}

/** 보드 요약. `PerformanceBoard`가 그대로 읽는다 — 예금 고유의 칸이 더 있다(FR-035). */
export interface DepositSummary extends SimulationSummary {
  currentTerm: DepositCurrentTerm | null;
  /** 잠정 회차가 시작된 날. 없으면 `null`(FR-007, FR-024). */
  provisionalFrom: string | null;
  /** 결측으로 멈췄을 때만(FR-019). 이때 `isFinal: false`, `asOf`는 그 만기일이다. */
  stopped: { date: string; reason: "rate_missing"; month: string } | null;
  /** 오늘 금리 확인이 실패했을 때만(FR-016). */
  recheckFailed: { kind: DepositFailureKind; reason: string } | null;
}

export interface DepositCondition {
  start: string;
  principal: DecimalString;
  interestTaxRate: DecimalString;
}

export interface DepositSimulationResponse {
  institution: { key: DepositInstitutionKey; name: string };
  condition: DepositCondition;
  summary: DepositSummary;
  terms: DepositTerm[];
  rows: DepositRow[];
}

/** 수집 중(202). 결과를 싣지 않는다(FR-011). */
export interface DepositCollecting {
  status: "collecting";
  institution: DepositInstitutionKey;
  jobId: number;
  missingFrom: string;
  missingThrough: string;
  progressUrl: string;
}

/** 시작일이 투자처의 첫 달보다 이르다(409, FR-006). */
export interface BeforeFirstMonthBody {
  status: "before_first_month";
  message: string;
  startableFrom: string;
}

/** 예금 이자 소득세율 (008 FR-030). 주식·가상자산 설정과 따로다. */
export interface DepositSettings {
  interestTaxRate: DecimalString;
  isDefault: boolean;
}

/**
 * 예금 이력 한 줄 (008 FR-037). **조건만** 담는다 — 결과는 금리·세율의 함수라 바뀐다(005 R5-9). 주식·가상자산 이력과 따로 둔다.
 */
export interface DepositHistoryEntry {
  id: string;
  institution: DepositInstitutionKey;
  start: string;
  principal: DecimalString;
  savedAt: string;
}

/* ───────────────────────── 009: 부동산 투자 시뮬레이션 ───────────────────────── */

/** 행정구역 단계 — 시·도 · 시·군·구 · 법정동(contracts/rest-api `regions`). 서버의 값 그대로다. */
export type RealEstateRegionLevel = "sido" | "sgg" | "umd";

/** 행정구역 한 줄. 현존 코드만 온다(FR-002). 시·군·구는 일반시 아래 구를 "수원시 장안구"처럼 붙인 이름이다. */
export interface RealEstateRegion {
  code: string;
  name: string;
  level: RealEstateRegionLevel;
}

export interface RealEstateRegionsResponse {
  items: RealEstateRegion[];
  refreshedAt: string | null;
}

/** 행정구역을 한 번도 받지 않았다(202). 화면은 진행을 보이고 끝나면 다시 요청한다(FR-015). */
export interface RealEstateRegionCollecting {
  status: "collecting";
  kind: "region";
  jobId: number;
  progressUrl: string;
}

/** 수집 실패 종류(FR-014). 할 일이 다르다(ui-wireframes E9). */
export type RealEstateFailureKind = "auth" | "rate_limited" | "format" | "network";

/** 실패 종류와 사유. 사유에 인증키가 없다(FR-013). */
export interface RealEstateFailure {
  kind: RealEstateFailureKind;
  reason: string;
}

/**
 * 단지 한 줄(FR-003). 모르는 값은 `null`이다 — 지어내지 않는다. `jibun`은 같은 동의 같은 이름 단지를 가를 때 쓴다.
 * `sources`는 단지 목록 자료(`kapt`)·실거래(`trade`) 중 어디에 있었는가.
 */
export interface RealEstateComplex {
  complexId: number;
  name: string;
  jibun: string | null;
  moveInYear: number | null;
  households: number | null;
  sources: Array<"kapt" | "trade">;
}

/** 그 시·군·구의 실거래 상태. `collected`는 첫 달부터 잠정 기간 앞 달까지 모두 받은 시·군·구다(data-model 5절). */
export type RealEstateTradesState = "none" | "collecting" | "collected" | "failed";

export interface RealEstateTrades {
  state: RealEstateTradesState;
  jobId: number | null;
  monthsDone: number;
  monthsTotal: number;
  progressUrl: string | null;
  /** `failed`일 때만 — 다시 열어도 사유가 보인다(FR-014). */
  failure: RealEstateFailure | null;
}

/** 단지 목록. 기본 정보(세대수·입주년도) 진행의 작업 번호는 `details.progressUrl`에만 있다. */
export interface RealEstateComplexesResponse {
  umd: { code: string; name: string; lawdCd: string };
  items: RealEstateComplex[];
  details: { pending: boolean; progressUrl: string | null };
  trades: RealEstateTrades;
  /** 단지 목록 자료를 받지 못했다 — 실거래 단지만 온다(FR-015). */
  listError?: RealEstateFailure;
}

/** 평형 구분 키(FR-004). 화면 순서다. */
export type RealEstateAreaKey = "10" | "20" | "30k" | "30l" | "40" | "50" | "60";

/**
 * 평형 구분 하나. 면적은 문자열(㎡)이고 경계가 없는 쪽은 `null`이다. 아래 경계의 포함 여부는 오지 않는다 — 구분이 빈틈없이
 * 이어지므로 앞 구분의 `maxInclusive`의 반대다. 거래 수·첫 달은 해제·사라짐을 뺀 값이다.
 */
export interface RealEstateAreaBucket {
  key: RealEstateAreaKey;
  label: string;
  minArea: DecimalString | null;
  maxArea: DecimalString | null;
  maxInclusive: boolean;
  trades: number;
  firstMonth: string | null;
  lastMonth: string | null;
  startableFrom: string | null;
}

export interface RealEstateAreasResponse {
  complexId: number;
  taxRulesFrom: string;
  /** 일곱 구분을 늘 모두 준다(거래 0인 구분 포함). */
  buckets: RealEstateAreaBucket[];
}

/** 그 시·군·구의 실거래를 받는 중(202) — 평형·시뮬레이션 요청. 결과를 싣지 않는다(FR-011). */
export interface RealEstateTradeCollecting {
  status: "collecting";
  kind: "trade";
  lawdCd: string;
  jobId: number;
  monthsDone: number;
  monthsTotal: number;
  progressUrl: string;
}
