/**
 * 비교 조건 (013 T030) — FR-004, FR-007, FR-012a, data-model 2.
 *
 * 정규 조건은 저장 본문(서버 `api/services/comparison_conditions`)과 같은 모양이다. 화면은 이것으로 "지금 조건 = 결과를 낸 조건"을
 * 가른다 — 다르면 결과를 흐린다(명확화 6). 대상 차례도 조건이다. 표의 정렬은 조건이 아니다.
 */
import { INSTITUTION_NAMES } from "@/stores/depositStore";
import type {
  CompareAsset,
  CompareMethod,
  CompareTarget,
  CryptoTarget,
  DepositTarget,
  Frequency,
  PrincipalCurrency,
  RealEstateTarget,
  StockTarget,
} from "./types";

export interface CompareInput {
  asset: CompareAsset;
  method: CompareMethod;
  frequency: Frequency;
  start: string;
  /** 쉼표 없는 금액 문자열 — 일시금 원금·한 번 납입액·월 납입액. 부동산은 쓰지 않는다. */
  amount: string;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean;
  targets: CompareTarget[];
}

export interface CompareCondition {
  v: 1;
  asset: CompareAsset;
  method: CompareMethod;
  frequency: Frequency | null;
  start: string;
  amount: string | null;
  principalCurrency: PrincipalCurrency;
  reinvest: boolean | null;
  targets: CompareTarget[];
}

export const ASSET_LABEL: Record<CompareAsset, string> = {
  stock: "주식", crypto: "가상자산", deposit: "예금", realestate: "부동산",
};

export const METHOD_LABEL: Record<CompareMethod, string> = {
  lump_sum: "일시금", recurring: "적립식", deposit: "정기예금", installment: "정기 적금", hold: "매입 후 보유",
};

const METHODS: Record<CompareAsset, CompareMethod[]> = {
  stock: ["lump_sum", "recurring"],
  crypto: ["lump_sum", "recurring"],
  deposit: ["deposit", "installment"],
  realestate: ["hold"],
};

/** 그 자산군에서 고를 수 있는 방식 — 첫째가 기본이다. */
export function methodsFor(asset: CompareAsset): CompareMethod[] {
  return METHODS[asset];
}

/** 대상 수의 끝 — 10개, 예금은 투자처가 다섯이다(FR-004, spec 경계 사례). */
export function maxTargets(asset: CompareAsset): number {
  return asset === "deposit" ? 5 : 10;
}

const isStock = (t: CompareTarget): t is StockTarget => "market" in t;
const isCrypto = (t: CompareTarget): t is CryptoTarget => "coinId" in t;
const isDeposit = (t: CompareTarget): t is DepositTarget => "institution" in t;

/** 같은 대상인지 가르는 키 — 주식 `market|symbol`, 가상자산 `coinId`, 예금 투자처, 부동산 `complexId|area`. */
export function targetKey(target: CompareTarget): string {
  if (isStock(target)) return `${target.market}|${target.symbol}`;
  if (isCrypto(target)) return String(target.coinId);
  if (isDeposit(target)) return target.institution;
  return `${target.complexId}|${target.area}`;
}

/** 화면에 보이는 대상 이름. */
export function targetName(target: CompareTarget): string {
  if (isStock(target)) return target.name;
  if (isCrypto(target)) return target.nameKo ?? target.name;
  if (isDeposit(target)) return INSTITUTION_NAMES[target.institution];
  return `${target.name} ${target.areaLabel}`;
}

/** 대상의 알려진 칸만 남긴다 — 검색 결과의 순위 같은 것은 조건이 아니다. */
function cleanTarget(target: CompareTarget): CompareTarget {
  if (isStock(target)) {
    const { market, symbol, name, currency } = target;
    return { market, symbol, name, currency };
  }
  if (isCrypto(target)) {
    const { coinId, symbol, name, nameKo, currency } = target;
    return { coinId, symbol, name, nameKo, currency };
  }
  if (isDeposit(target)) return { institution: target.institution };
  const { complexId, name, umdName, area, areaLabel } = target as RealEstateTarget;
  return { complexId, name, umdName, area, areaLabel };
}

/** 입력 → 정규 조건(data-model 2). */
export function toCondition(input: CompareInput): CompareCondition {
  const krwOnly = input.asset === "deposit" || input.asset === "realestate";
  return {
    v: 1,
    asset: input.asset,
    method: input.method,
    frequency: input.method === "recurring" ? input.frequency : null,
    start: input.start,
    amount: input.asset === "realestate" ? null : input.amount,
    principalCurrency: krwOnly ? "KRW" : input.principalCurrency,
    reinvest: input.asset === "stock" ? input.reinvest : null,
    targets: input.targets.map(cleanTarget),
  };
}

/** 키 차례를 고정한 직렬화 — 같은 조건이면 같은 글이다. */
function stable(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
    return `{${entries.map(([k, v]) => `${JSON.stringify(k)}:${stable(v)}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

/** 두 정규 조건이 같은가. 결과가 없으면(`null`) 같지 않다. */
export function sameCondition(a: CompareCondition | null, b: CompareCondition | null): boolean {
  if (a === null || b === null) return false;
  return stable(a) === stable(b);
}

/** 자동 이름 — "{자산군} {대상 수}개 · {시작일} · {방식}"(FR-016). */
export function autoName(condition: CompareCondition): string {
  return `${ASSET_LABEL[condition.asset]} ${condition.targets.length}개 · ${condition.start} · ${METHOD_LABEL[condition.method]}`;
}

const SELECTABLE: readonly PrincipalCurrency[] = ["KRW", "USD", "JPY"];

/**
 * 고를 수 있는 원금 통화 — 원화는 늘 되고, 외화는 **모든 대상의 통화가 그 통화일 때만** 된다(006 규칙을 대상 열에 — FR-007). 예금·
 * 부동산은 원화뿐이다.
 */
export function allowedCurrencies(asset: CompareAsset, targets: CompareTarget[]): PrincipalCurrency[] {
  if (asset === "deposit" || asset === "realestate" || targets.length === 0) return ["KRW"];
  const currencies = new Set(targets.map((t) => (isStock(t) || isCrypto(t) ? t.currency : "KRW")));
  if (currencies.size !== 1) return ["KRW"];
  const [only] = [...currencies];
  const own = SELECTABLE.find((c) => c === only);
  return own === undefined || own === "KRW" ? ["KRW"] : ["KRW", own];
}
