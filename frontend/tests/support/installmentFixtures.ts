/**
 * 정기 적금 화면 테스트 공용 응답 (011) — contracts/rest-api §3·§4의 모양. 값은 백엔드 단위 테스트의 손계산(시중은행, 2015-01-15, 월
 * 1,000,000원)에서 가져왔다.
 */
import type {
  DepositCollecting,
  DepositInstitutionsResponse,
  InstallmentResponse,
  InstallmentRow,
  InstallmentSummary,
} from "@/lib/types";

const NONE = "출처(ECOS)에 이 투자처의 정기적금 금리 통계가 없습니다.";

export const INSTALLMENT_INSTITUTIONS: DepositInstitutionsResponse = {
  institutions: [
    { key: "commercial_bank", name: "시중은행", description: "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함",
      firstMonth: "2012-01", latestMonth: "2026-08", checkedOn: "2026-10-04",
      installment: { available: true, description: "예금은행 정기적금(1~2년 만기) 평균", firstMonth: "2003-01",
        latestMonth: "2026-08", checkedOn: "2026-10-04", startableFrom: "2011-01-01" } },
    { key: "savings_bank", name: "저축은행", description: "상호저축은행 정기예금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null, installment: { available: false, reason: NONE } },
    { key: "credit_union", name: "신협", description: "신협 정기예탁금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null, installment: { available: false, reason: NONE } },
    { key: "mutual_finance", name: "상호금융", description: "상호금융 정기예탁금(1년만기) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null,
      installment: { available: true, description: "상호금융 정기적금 평균 — 만기 구분 없음", firstMonth: null,
        latestMonth: null, checkedOn: null, startableFrom: null } },
    { key: "saemaul", name: "새마을금고", description: "새마을금고 정기예탁금(1년) 평균",
      firstMonth: null, latestMonth: null, checkedOn: null, installment: { available: false, reason: NONE } },
  ],
  source: "한국은행 경제통계시스템(ECOS)",
  basis: "신규취급액 기준 가중평균",
};

export const UNAVAILABLE_REASON = NONE;

const row = (over: Partial<InstallmentRow>): InstallmentRow => ({
  date: "2018-01-15", kind: "installment", contractNo: 4, installmentNo: 1, amount: "1000000", rate: "1.82",
  rateMonth: "2018-01", provisional: false, contributed: "37000000", installmentValue: "1000000",
  depositValue: "36811149", balance: "37811149", profit: "811149", returnRate: "0.021923", ...over,
});

export const ROWS: InstallmentRow[] = [
  row({}),
  row({ kind: "deposit_join", contractNo: 3, installmentNo: undefined, amount: "36811149", rate: "1.93",
    fromDeposit: "24728664", fromInstallment: "12082485", contributed: "36000000", installmentValue: "0",
    balance: "36811149", profit: "811149", returnRate: "0.022532" }),
  row({ kind: "deposit_maturity", contractNo: 2, installmentNo: undefined, amount: "24728664", rate: "1.58",
    rateMonth: "2017-01", interest: "385559", tax: "59376", afterTax: "326183", contributed: "36000000",
    installmentValue: "12082485", depositValue: "24728664", balance: "36811149", profit: "811149",
    returnRate: "0.022532" }),
  row({ kind: "installment_maturity", contractNo: 3, installmentNo: undefined, amount: "12082485", rate: "1.5",
    rateMonth: "2017-01", interest: "97500", tax: "15015", afterTax: "82485", contributed: "36000000",
    installmentValue: "12082485", depositValue: "24728664", balance: "36811149", profit: "811149",
    returnRate: "0.022532" }),
  row({ date: "2018-01-01", kind: "month", contractNo: null, installmentNo: undefined, amount: undefined,
    rate: undefined, rateMonth: undefined, contributed: "36000000", installmentValue: "12067700",
    depositValue: "24697000", balance: "36764700", profit: "764700", returnRate: "0.021242" }),
  row({ date: "2015-01-15", contractNo: 1, rate: "2.32", rateMonth: "2015-01", contributed: "1000000",
    installmentValue: "1000000", depositValue: "0", balance: "1000000", profit: "0", returnRate: "0.000000" }),
];

export const SUMMARY: InstallmentSummary = {
  contributed: "37000000", installments: 37, interestTotal: "958803", taxTotal: "147654", afterTaxTotal: "811149",
  installmentAfterTax: "308495", depositAfterTax: "502654",
  installmentValue: "1000000", depositValue: "36811149", balance: "37811149", profit: "811149",
  returnRate: "0.021923", asOf: "2018-01-15", isFinal: true,
  currentInstallment: { no: 4, joinedOn: "2018-01-15", maturesOn: "2019-01-15", rate: "1.82", rateMonth: "2018-01",
    provisional: false, paid: 1 },
  currentDeposit: { no: 3, joinedOn: "2018-01-15", maturesOn: "2019-01-15", rate: "1.93", rateMonth: "2018-01",
    provisional: false, principal: "36811149" },
  provisionalFrom: null, stopped: null, recheckFailed: null,
};

export const INSTALLMENT_RESULT: InstallmentResponse = {
  institution: { key: "commercial_bank", name: "시중은행" },
  condition: { product: "installment", start: "2015-01-15", amount: "1000000", interestTaxRate: "0.154000",
    installmentItem: "예금은행 정기적금(1~2년 만기) 평균",
    depositItem: "예금은행 정기예금(1년) 평균 — 일반·특수은행 포함" },
  summary: SUMMARY,
  contracts: [
    { no: 1, joinedOn: "2015-01-15", maturesOn: "2016-01-15", rate: "2.32", rateMonth: "2015-01", provisional: false,
      monthly: "1000000", paid: 12, interest: "150800", tax: "23223", afterTax: "127577", amount: "12127577" },
  ],
  deposits: [
    { no: 1, joinedOn: "2016-01-15", maturesOn: "2017-01-15", rate: "1.72", rateMonth: "2016-01", provisional: false,
      principal: "12127577", fromDeposit: "0", fromInstallment: "12127577", interest: "208594", tax: "32123",
      afterTax: "176471" },
  ],
  rows: ROWS,
};

export const INSTALLMENT_COLLECTING: DepositCollecting = {
  status: "collecting", institution: "commercial_bank", series: "installment", jobId: 41, missingFrom: "2015-01",
  missingThrough: "2026-10", progressUrl: "/api/deposit/progress?jobId=41",
};

export const DEPOSIT_COLLECTING: DepositCollecting = {
  ...INSTALLMENT_COLLECTING, series: "deposit", jobId: 42, missingFrom: "2016-01",
  progressUrl: "/api/deposit/progress?jobId=42",
};
