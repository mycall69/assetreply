/**
 * 예금 화면 테스트 공용 응답 (008) — contracts/rest-api의 모양, 값은 research R8-7 참조값 1(시중은행, 2020-01-15, 1,000만 원,
 * 오늘 2026-10-04)에서 가져왔다.
 */
import type {
  DepositCollecting,
  DepositInstitutionsResponse,
  DepositRow,
  DepositSimulationResponse,
} from "@/lib/types";

export const INSTITUTIONS: DepositInstitutionsResponse = {
  institutions: [
    { key: "commercial_bank", name: "시중은행", description: "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함",
      firstMonth: "2012-01", latestMonth: "2026-08", checkedOn: "2026-10-04" },
    { key: "savings_bank", name: "저축은행", description: "상호저축은행 정기예금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null },
    { key: "credit_union", name: "신협", description: "신협 정기예탁금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null },
    { key: "mutual_finance", name: "상호금융", description: "상호금융 정기예탁금(1년만기) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null },
    { key: "saemaul", name: "새마을금고", description: "새마을금고 정기예탁금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null },
  ],
  source: "한국은행 경제통계시스템(ECOS)",
  basis: "신규취급액 기준 가중평균",
};

const row = (over: Partial<DepositRow>): DepositRow => ({
  date: "2026-10-01", kind: "month", rate: "2.84", rateMonth: "2026-01", provisional: false,
  principal: "11361267", interest: "228955", tax: "35259", afterTax: "193696",
  balance: "11554963", profit: "1554963", returnRate: "0.155496", ...over,
});

export const ROWS: DepositRow[] = [
  row({}),
  row({ date: "2026-01-15", kind: "reinvest", interest: "0", tax: "0", afterTax: "0",
    balance: "11361267", profit: "1361267", returnRate: "0.136127" }),
  row({ date: "2026-01-15", kind: "maturity", rate: "3.06", rateMonth: "2025-01", principal: "11074573",
    interest: "338881", tax: "52187", afterTax: "286694", balance: "11361267", profit: "1361267",
    returnRate: "0.136127" }),
  row({ date: "2020-01-15", kind: "join", rate: "1.62", rateMonth: "2020-01", principal: "10000000",
    interest: "0", tax: "0", afterTax: "0", balance: "10000000", profit: "0", returnRate: "0.000000" }),
];

export const RESULT: DepositSimulationResponse = {
  institution: { key: "commercial_bank", name: "시중은행" },
  condition: { start: "2020-01-15", principal: "10000000", interestTaxRate: "0.154000" },
  summary: {
    principal: "10000000", profit: "1557207", returnRate: "0.155721", asOf: "2026-10-04", isFinal: true,
    currentTerm: { joinedOn: "2026-01-15", maturesOn: "2027-01-15", rate: "2.84", rateMonth: "2026-01",
      principal: "11361267", provisional: false },
    provisionalFrom: null, stopped: null, recheckFailed: null,
  },
  terms: [
    { no: 1, joinedOn: "2020-01-15", maturesOn: "2021-01-15", rate: "1.62", rateMonth: "2020-01",
      provisional: false, principal: "10000000", interest: "162000", tax: "24948", afterTax: "137052" },
  ],
  rows: ROWS,
};

/** 시작 달이 미발표라 마지막 발표 달(2026-08) 금리로 잠정 가입한 결과. */
export const PROVISIONAL: DepositSimulationResponse = {
  ...RESULT,
  condition: { ...RESULT.condition, start: "2026-09-15" },
  summary: {
    ...RESULT.summary, profit: "14929", returnRate: "0.001493",
    currentTerm: { joinedOn: "2026-09-15", maturesOn: "2027-09-15", rate: "3.39", rateMonth: "2026-08",
      principal: "10000000", provisional: true },
    provisionalFrom: "2026-09-15",
  },
  terms: [],
  rows: [
    row({ date: "2026-10-01", rate: "3.39", rateMonth: "2026-08", provisional: true, principal: "10000000",
      interest: "14860", tax: "2288", afterTax: "12572", balance: "10012572", profit: "12572",
      returnRate: "0.001257" }),
    row({ date: "2026-09-15", kind: "join", rate: "3.39", rateMonth: "2026-08", provisional: true,
      principal: "10000000", interest: "0", tax: "0", afterTax: "0", balance: "10000000", profit: "0",
      returnRate: "0.000000" }),
  ],
};

export const COLLECTING: DepositCollecting = {
  status: "collecting", institution: "commercial_bank", jobId: 3, missingFrom: "2020-01",
  missingThrough: "2026-10", progressUrl: "/api/deposit/progress?jobId=3",
};
