/**
 * 부동산 화면 테스트 공용 응답 (009 T020) — contracts/rest-api `regions`·`complexes`·`complexes/{id}/areas`의 모양.
 *
 * 값은 실측(송파구 가락동·헬리오시티, 2020-01~2023-09)에서 가져왔다 — 헬리오시티의 평형별 거래 수(해제 제외)는 백엔드
 * `test_realestate_lists_api.py`와 같다. 행정구역 코드도 실제 법정동 코드다(서울 `1100000000`, 송파구 `1171000000`, 가락동
 * `1171010700`). 단계 이름은 서버와 같다 — `sido`·`sgg`·`umd`.
 *
 * **이 파일이 전제하는 형식**(`@/lib/types`, T026이 더한다):
 * `RealEstateRegionLevel`·`RealEstateRegion`·`RealEstateRegionsResponse`·`RealEstateRegionCollecting`·`RealEstateFailureKind`·
 * `RealEstateFailure`·`RealEstateComplex`·`RealEstateTrades`·`RealEstateComplexesResponse`·`RealEstateAreaKey`·
 * `RealEstateAreaBucket`·`RealEstateAreasResponse`·`RealEstateTradeCollecting`. 필드는 rest-api 계약의 JSON 그대로다.
 *
 * **이 파일이 전제하는 상태**(`@/stores/realEstateStore`의 `useRealEstateStore`) — `resetRealEstateStore`의 필드 목록을 본다.
 * 결과 필드(`summary`·`rows`)의 모양은 Phase 4(T034·T039)가 정한다. 여기서는 **비워지는지**만 본다(SC-007).
 */
import { vi } from "vitest";
import { apiClient } from "@/lib/apiClient";
import type {
  RealEstateAreaBucket,
  RealEstateAreaKey,
  RealEstateAreasResponse,
  RealEstateComplex,
  RealEstateComplexesResponse,
  RealEstateFailureKind,
  RealEstateRegion,
  RealEstateRegionCollecting,
  RealEstateRegionLevel,
  RealEstateRegionsResponse,
  RealEstateTradeCollecting,
  RealEstateTrades,
} from "@/lib/types";
import { useRealEstateStore } from "@/stores/realEstateStore";

export const SEOUL = "1100000000";
export const GYEONGGI = "4100000000";
export const GANGNAM = "1168000000";
export const SONGPA = "1171000000";
export const GARAK = "1171010700";
export const MUNJEONG = "1171010800";
export const HELIO_ID = 12;

const REFRESHED_AT = "2023-10-05T03:00:00Z";

const region = (code: string, name: string, level: RealEstateRegionLevel): RealEstateRegion =>
  ({ code, name, level });

/** 시·도 — 가나다순(서버가 정렬한다). */
export const SIDOS: RealEstateRegionsResponse = {
  items: [region("5100000000", "강원특별자치도", "sido"), region(GYEONGGI, "경기도", "sido"),
    region(SEOUL, "서울특별시", "sido")],
  refreshedAt: REFRESHED_AT,
};
export const SEOUL_SGGS: RealEstateRegionsResponse = {
  items: [region(GANGNAM, "강남구", "sgg"), region(SONGPA, "송파구", "sgg")],
  refreshedAt: REFRESHED_AT,
};
/** 일반시 아래 구는 "수원시 장안구"처럼 붙인 이름이다(rest-api `regions`). */
export const GYEONGGI_SGGS: RealEstateRegionsResponse = {
  items: [region("4113500000", "성남시 분당구", "sgg"), region("4111100000", "수원시 장안구", "sgg")],
  refreshedAt: REFRESHED_AT,
};
export const SONGPA_UMDS: RealEstateRegionsResponse = {
  items: [region(GARAK, "가락동", "umd"), region(MUNJEONG, "문정동", "umd")],
  refreshedAt: REFRESHED_AT,
};
export const GANGNAM_UMDS: RealEstateRegionsResponse = {
  items: [region("1168010300", "개포동", "umd"), region("1168010100", "역삼동", "umd")],
  refreshedAt: REFRESHED_AT,
};

/** 행정구역을 한 번도 받지 않았다(202). */
export const REGION_COLLECTING: RealEstateRegionCollecting = {
  status: "collecting", kind: "region", jobId: 7, progressUrl: "/api/realestate/progress?jobId=7",
};

export const HELIO: RealEstateComplex = {
  complexId: HELIO_ID, name: "헬리오시티", jibun: "913", moveInYear: 2018, households: 9510, sources: ["kapt", "trade"],
};
/** 같은 동에 이름이 같은 단지 둘 — 화면이 항목 끝의 지번으로 가른다(FR-003, E1). */
export const HYUNDAI_OLD: RealEstateComplex = {
  complexId: 41, name: "현대", jibun: "140", moveInYear: 1998, households: 500, sources: ["kapt", "trade"],
};
export const HYUNDAI_NEW: RealEstateComplex = {
  complexId: 42, name: "현대", jibun: "140-2", moveInYear: 2003, households: null, sources: ["trade"],
};
/** 실거래에만 있는 단지 — 세대수를 모른다(지어내지 않는다). */
export const HYUNJIN: RealEstateComplex = {
  complexId: 31, name: "현진타워", jibun: "171", moveInYear: 2015, households: null, sources: ["trade"],
};

export const COLLECTED_TRADES: RealEstateTrades = {
  state: "collected", jobId: null, monthsDone: 250, monthsTotal: 250, progressUrl: null, failure: null,
};
export const COLLECTING_TRADES: RealEstateTrades = {
  state: "collecting", jobId: 9, monthsDone: 120, monthsTotal: 250,
  progressUrl: "/api/realestate/progress?jobId=9", failure: null,
};
export const failedTrades = (kind: RealEstateFailureKind, reason = "출처가 준 사유"): RealEstateTrades => ({
  state: "failed", jobId: null, monthsDone: 120, monthsTotal: 250, progressUrl: null, failure: { kind, reason },
});

/** 가락동 — 기본 정보와 실거래를 다 받았다. 정렬은 서버가 한다(가구수 내림차순, 모르면 뒤). */
export const GARAK_COMPLEXES: RealEstateComplexesResponse = {
  umd: { code: GARAK, name: "가락동", lawdCd: "11710" },
  items: [HELIO, HYUNDAI_OLD, HYUNDAI_NEW, HYUNJIN],
  details: { pending: false, progressUrl: null },
  trades: COLLECTED_TRADES,
};

export const complexesWith = (over: Partial<RealEstateComplexesResponse>): RealEstateComplexesResponse =>
  ({ ...GARAK_COMPLEXES, ...over });

/**
 * 가락동을 처음 고른 때 — 단지 목록 자료의 이름만 있고, 기본 정보(작업 11)와 송파구 실거래(작업 9)를 받는 중이다. 기본 정보 진행의
 * 작업 번호는 `details.progressUrl`의 `jobId`에만 있다(rest-api `complexes`).
 */
export const GARAK_FIRST: RealEstateComplexesResponse = complexesWith({
  items: [{ ...HELIO, moveInYear: null, households: null, sources: ["kapt"] }],
  details: { pending: true, progressUrl: "/api/realestate/progress?jobId=11" },
  trades: COLLECTING_TRADES,
});

export const MUNJEONG_COMPLEXES: RealEstateComplexesResponse = complexesWith({
  umd: { code: MUNJEONG, name: "문정동", lawdCd: "11710" },
  items: [{ complexId: 51, name: "올림픽훼밀리타운", jibun: "150", moveInYear: 1988, households: 4494,
    sources: ["kapt", "trade"] }],
});

const bucket = (
  key: RealEstateAreaKey, label: string, minArea: string | null, maxArea: string | null, maxInclusive: boolean,
  trades: number, firstMonth: string | null,
): RealEstateAreaBucket => ({
  key, label, minArea, maxArea, maxInclusive, trades, firstMonth,
  lastMonth: firstMonth === null ? null : "2023-09",
  startableFrom: firstMonth === null ? null : `${firstMonth}-01`,
});

/** 헬리오시티의 일곱 구분 — 50평대·60평대 이상은 거래가 없다(서버는 0건인 구분도 늘 준다). */
export const HELIO_AREAS: RealEstateAreasResponse = {
  complexId: HELIO_ID,
  taxRulesFrom: "2006-01-01",
  buckets: [
    bucket("10", "10평대", null, "50", false, 101, "2020-01"),
    bucket("20", "20평대", "50", "70", false, 72, "2020-01"),
    bucket("30k", "30평대(국평)", "70", "85", true, 301, "2020-02"),
    bucket("30l", "30평대(대형)", "85", "105", false, 27, "2020-03"),
    bucket("40", "40평대", "105", "135", false, 30, "2020-01"),
    bucket("50", "50평대", "135", "165", false, 0, null),
    bucket("60", "60평대 이상", "165", null, false, 0, null),
  ],
};

/** 실거래를 아직 받지 않은 단지의 평형 요청(202). */
export const AREAS_COLLECTING: RealEstateTradeCollecting = {
  status: "collecting", kind: "trade", lawdCd: "11710", jobId: 9, monthsDone: 0, monthsTotal: 46,
  progressUrl: "/api/realestate/progress?jobId=9",
};

export const FAILURE_KINDS: RealEstateFailureKind[] = ["auth", "rate_limited", "format", "network"];

/**
 * E9 표 — 종류마다 **문구와 할 일**이 다르다(FR-014). 사유를 하나로 뭉치면 기다리면 되는지 인증키를 고쳐야 하는지 모른다.
 * 행정구역 실패(E2)도 같은 표를 쓰므로 "실거래"가 들어가지 않는 조각만 둔다. 실거래 한도의 "내일 다시 실행"은 단지 쪽 테스트가 본다.
 */
export const FAILURE_FRAGMENTS: Record<RealEstateFailureKind, string[]> = {
  auth: ["공공데이터포털 인증에 실패했습니다", "인증키 설정과 활용신청을 확인하세요"],
  rate_limited: ["하루 호출 한도에 닿았습니다", "받은 데까지 남겼습니다"],
  format: ["출처의 응답 형식이 바뀌었습니다", "어댑터를 고쳐야 합니다"],
  network: ["출처에 연결하지 못했습니다", "다시 실행하면 이어서 받습니다"],
};

/** 결과가 있는 상태를 흉내 낸다. 모양은 Phase 4가 정한다 — 여기서는 비워지는지만 본다. */
export const RESULT_PLACEHOLDER = {
  summary: { profit: "1" } as never,
  rows: [{ date: "2026-10-01" }] as never[],
};

/** 경로 → 응답. `undefined`면 처리기가 없는 경로, `Error`면 거절, `Promise`면 그대로 기다린다. */
export function routeRealEstate(answer: (path: string) => unknown) {
  return vi.spyOn(apiClient, "get").mockImplementation(((path: string) => {
    const result = answer(path);
    if (result === undefined) return Promise.reject(new Error(`처리기가 없는 경로: ${path}`));
    return result instanceof Error ? Promise.reject(result) : Promise.resolve(result);
  }) as typeof apiClient.get);
}

/** 경로의 앞부분과 질의 매개변수. 질의의 순서·빈 `parent=`의 유무에 기대지 않는다. */
export function splitPath(path: string): { base: string; params: URLSearchParams } {
  const [base, query = ""] = path.split("?");
  return { base, params: new URLSearchParams(query) };
}

/** 모두 받아 둔 상태의 응답 — 시·도 · 시·군·구 · 동 · 단지(가락동·문정동) · 평형(헬리오시티). */
export function realEstateRoutes(path: string): unknown {
  const { base, params } = splitPath(path);
  if (base === "/api/realestate/regions") {
    const lists: Record<string, RealEstateRegionsResponse> = {
      "": SIDOS, [SEOUL]: SEOUL_SGGS, [GYEONGGI]: GYEONGGI_SGGS, [SONGPA]: SONGPA_UMDS, [GANGNAM]: GANGNAM_UMDS,
    };
    return lists[params.get("parent") ?? ""];
  }
  if (base === "/api/realestate/complexes") {
    const umd = params.get("umd");
    return umd === GARAK ? GARAK_COMPLEXES : umd === MUNJEONG ? MUNJEONG_COMPLEXES : undefined;
  }
  if (base === `/api/realestate/complexes/${HELIO_ID}/areas`) return HELIO_AREAS;
  return undefined;
}

/** 처음 연 화면의 상태. **이 필드 목록이 스토어가 가져야 할 상태다**(T026). */
export function resetRealEstateStore(): void {
  useRealEstateStore.getState().dispose();
  useRealEstateStore.setState({
    regions: { sido: null, sgg: null, umd: null },
    selection: { sido: null, sgg: null, umd: null, complexId: null, area: null },
    regionCollecting: null, regionProgress: null, regionFailure: null,
    complexes: null, tradeProgress: null, detailsProgress: null,
    areas: null, areasCollecting: null,
    summary: null, rows: [], error: null,
  });
}

/** 서울특별시 → 송파구 → 가락동 → 헬리오시티 → 30평대(국평)까지 고르고 결과까지 있는 상태. */
export function chooseHelio(): void {
  useRealEstateStore.setState({
    regions: { sido: SIDOS.items, sgg: SEOUL_SGGS.items, umd: SONGPA_UMDS.items },
    selection: { sido: SEOUL, sgg: SONGPA, umd: GARAK, complexId: HELIO_ID, area: "30k" },
    complexes: GARAK_COMPLEXES, areas: HELIO_AREAS, ...RESULT_PLACEHOLDER,
  });
}
