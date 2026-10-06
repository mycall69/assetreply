/**
 * 외환 화면의 단일 상태 원천 (T018, T034) — contracts/ui-interaction.md.
 *
 * 날짜 입력·차트 강조선·표 강조 행은 **각자 상태를 갖지 않는다.** 셋 다 여기의 같은 값을
 * 읽어 그린다. 각자 상태를 두고 서로 동기화하면 어긋나는 순간이 반드시 생기고,
 * SC-002(세 영역이 다른 날짜를 가리키는 사례 0건)를 만족할 수 없다.
 */

import { create } from "zustand";
import { ApiError, apiClient, type CurrencyCode } from "@/lib/apiClient";
import type {
  CoverageRow,
  DailyResponse,
  LatestResponse,
  PeriodRow,
  PeriodUnit,
  SeriesCollecting,
  SeriesResponse,
} from "@/lib/types";

export type Preset =
  | "1m" | "6m" | "1y" | "5y" | "10y" | "20y" | "30y" | "40y" | "50y" | "all";

/**
 * 기간 프리셋. 일 단위 데이터에서 하루·일주일 구간은 표시할 점이 너무 적어 추이로서
 * 의미가 없으므로 제외했다 (spec Assumptions).
 *
 * 2026-09-27 반복에서 20·30·40·50년을 더했다. 10년과 전체 사이가 비어 있으면
 * USD(62년)에서 장기 추이를 볼 방법이 전체뿐이라, 구간을 좁혀 보려면 직접 지정해야 했다.
 */
export const PRESETS: ReadonlyArray<{ key: Preset; label: string }> = [
  { key: "1m", label: "1개월" },
  { key: "6m", label: "6개월" },
  { key: "1y", label: "1년" },
  { key: "5y", label: "5년" },
  { key: "10y", label: "10년" },
  { key: "20y", label: "20년" },
  { key: "30y", label: "30년" },
  { key: "40y", label: "40년" },
  { key: "50y", label: "50년" },
  { key: "all", label: "전체" },
];

/**
 * 프리셋이 거슬러 올라가는 길이. 표로 두는 이유는 `else if`가 아홉 개로 늘어나면
 * 한 줄만 빠뜨려도 그 프리셋이 조용히 "전체"로 떨어지기 때문이다.
 */
const MONTHS_BACK: Partial<Record<Preset, number>> = { "1m": 1, "6m": 6 };
const YEARS_BACK: Partial<Record<Preset, number>> = {
  "1y": 1, "5y": 5, "10y": 10, "20y": 20, "30y": 30, "40y": 40, "50y": 50,
};

function yesterday(): Date {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d;
}

const iso = (d: Date): string => d.toISOString().slice(0, 10);

/** 프리셋이 요구하는 시작일. `all`은 길이가 아니라 "축적 전부"라 `null`이다. */
function requestedStart(preset: Preset): string | null {
  const start = yesterday();
  const months = MONTHS_BACK[preset];
  if (months !== undefined) {
    start.setMonth(start.getMonth() - months);
    return iso(start);
  }
  const years = YEARS_BACK[preset];
  if (years !== undefined) {
    start.setFullYear(start.getFullYear() - years);
    return iso(start);
  }
  return null;
}

/** 통화의 축적이 시작되는 날. 최초 제공일을 모르면 수집 시작일을 바닥으로 쓴다. */
function coverageFloor(coverage: CoverageRow | null): string | null {
  return coverage?.firstAvailableDate ?? coverage?.coveredFrom ?? null;
}

/**
 * 프리셋 → 시작일. "전체"는 통화마다 다르므로 여기서 정할 수 없다(FR-002).
 * 커버리지에서 받은 값을 호출부가 채운다.
 */
export function presetStart(preset: Preset, coverage: CoverageRow | null): string {
  const wanted = requestedStart(preset);
  const floor = coverageFloor(coverage);
  if (wanted === null) return floor ?? iso(yesterday());

  // 프리셋이 요구하는 구간이 축적 시작일보다 이르면 실제 범위만 쓴다 (FR-019).
  return floor !== null && wanted < floor ? floor : wanted;
}

/**
 * 요청 구간이 축적 범위를 넘어 잘렸음을 알리는 안내 (FR-019, SC-012).
 *
 * **잘리지 않았으면 `null`이다.** 늘 알리면 안내가 배경 소음이 되어 진짜 잘린 경우를
 * 가린다. 반대로 알리지 않으면 EUR(1994~)에서 40년·50년·전체가 같은 차트를 그리는데
 * 이유를 알 수 없어, 사용자는 버튼이 먹지 않는다고 여긴다.
 *
 * 커버리지를 아직 모르면 알리지 않는다 — 모르는 것과 잘린 것은 다르다.
 */
export function presetClampNotice(
  preset: Preset,
  coverage: CoverageRow | null,
): RangeNotice | null {
  const wanted = requestedStart(preset);
  const floor = coverageFloor(coverage);
  if (wanted === null || floor === null || coverage === null) return null;
  if (wanted >= floor) return null;
  // 통화 코드 뒤에 조사를 붙이지 않는다 — USD는 "유에스디", EUR은 "이유알"로 읽혀
  // 받침이 갈린다. 쌍점으로 끊으면 조사 선택 자체가 없어진다.
  return {
    kind: "clamped_to_coverage",
    message: `${coverage.currency}: ${floor}부터 축적되어 있어 그 구간만 표시합니다.`,
  };
}

/**
 * 선택 날짜가 속한 구간의 행 (004 FR-019, research R4-7).
 *
 * **기준일만으로는 판정할 수 없다.** 주·월 단위에서 선택 날짜가 기준일인 경우가 오히려
 * 드물어, 기준일과 대조하면 강조가 거의 사라진다 — 사용자는 선택이 풀린 것으로
 * 오해한다. 그래서 행이 덮는 구간(`periodFrom`~`periodTo`)으로 판정한다.
 *
 * 순수 함수로 두는 이유는 이미 받은 행으로 답할 수 있는 질문이기 때문이다. 서버가
 * 판정하면 선택 날짜가 바뀔 때마다 재조회해야 한다.
 */
export function highlightedRow(
  daily: DailyResponse | null,
  selectedDate: string | null,
): PeriodRow | null {
  if (daily === null || selectedDate === null) return null;
  // ISO 날짜 문자열은 사전순 비교가 곧 시간순 비교다.
  return (
    daily.rows.find(
      (r) => r.periodFrom <= selectedDate && selectedDate <= r.periodTo,
    ) ?? null
  );
}

export interface RangeNotice {
  readonly kind: "out_of_range" | "clamped_to_coverage";
  readonly message: string;
}

interface FxWorkspaceState {
  currency: CurrencyCode;
  /** 화면 전체가 공유하는 하나의 선택 날짜 (FR-008). */
  selectedDate: string | null;
  preset: Preset;
  /** 표가 행을 고르는 기준 (004 FR-006). 화면 세션 안에서만 유지한다. */
  period: PeriodUnit;
  coverage: CoverageRow[];
  latest: LatestResponse | null;
  daily: DailyResponse | null;
  series: SeriesResponse | null;
  collecting: SeriesCollecting | null;
  notice: RangeNotice | null;
  /**
   * 프리셋이 축적 범위를 넘어 잘렸을 때의 안내 (FR-019). `notice`와 **따로 둔다** —
   * 그쪽은 선택 날짜에 대한 안내라 날짜 입력 아래에 나온다. 차트 이야기를 거기서 하면
   * 사용자가 무엇에 대한 말인지 알 수 없다.
   */
  presetNotice: RangeNotice | null;
  loading: boolean;
  error: string | null;
  /** 이어 보기가 진행 중인가. 중복 요청을 막는 첫 겹이다 (FR-005). */
  loadingMore: boolean;
  /**
   * 이어 보기 실패. `error`와 **따로 둔다** — 표 아래에서 말해야 할 일을 상단 경고로
   * 올리면 표가 멀쩡한데 화면이 고장 난 것처럼 보인다 (FR-004).
   */
  loadMoreError: string | null;
  /**
   * 먼 날짜를 골라 표를 통째로 새로 받을 때 증가한다. 화면은 이 값이 바뀌면 스크롤을 표의 처음으로 되돌린다(004 FR-005a·FR-005b).
   *
   * **기간 단위 전환은 올리지 않는다**(012 FR-001 — 004 FR-005b를 기간 전환에 한해 대체). 올리면 새 표가 붙은 뒤 창이 표의 처음으로 끌려가 사용자가
   * 누른 단위 탭이 화면 밖으로 밀려난다("화면이 위로 쑥 올라간다").
   */
  tableEpoch: number;

  coverageFor: (currency?: CurrencyCode) => CoverageRow | null;
  setCurrency: (c: CurrencyCode) => Promise<void>;
  setPreset: (p: Preset) => Promise<void>;
  setPeriod: (p: PeriodUnit) => Promise<void>;
  selectDate: (date: string) => Promise<void>;
  loadAll: () => Promise<void>;
  loadMoreDaily: () => Promise<void>;
  reloadRates: () => Promise<void>;
}

/** 선택 날짜가 조회 가능 범위 안인지 판정한다 (FR-010). 서버에 묻지 않는다. */
function checkRange(date: string, cov: CoverageRow | null): RangeNotice | null {
  if (cov === null) {
    return { kind: "out_of_range", message: "아직 수집된 데이터가 없습니다." };
  }
  const from = cov.firstAvailableDate ?? cov.coveredFrom;
  const to = cov.coveredThrough;
  if (date < from || date > to) {
    return {
      kind: "out_of_range",
      message: `조회 가능한 범위를 벗어났습니다. ${from} ~ ${to}`,
    };
  }
  return null;
}

const message = (err: unknown, fallback: string): string =>
  err instanceof ApiError ? err.message : fallback;

export const useFxWorkspaceStore = create<FxWorkspaceState>((set, get) => ({
  currency: "USD",
  selectedDate: null,
  preset: "1y",
  period: "daily",
  coverage: [],
  latest: null,
  daily: null,
  series: null,
  collecting: null,
  notice: null,
  presetNotice: null,
  loading: false,
  error: null,
  loadingMore: false,
  loadMoreError: null,
  tableEpoch: 0,

  coverageFor: (currency) => {
    const code = currency ?? get().currency;
    return get().coverage.find((c) => c.currency === code) ?? null;
  },

  /**
   * 커버리지를 받은 뒤 요약·표·차트 세 번의 병렬 호출 (research R2-6).
   *
   * **커버리지는 부를 때마다 새로 받는다**(`.specify/bugs/fx-stale-coverage`). 처음 한 번만 받아 두면 화면을 연 뒤
   * 수집된 통화의 행이 없어 차트가 하루짜리 구간을 요청해 안내 없이 비었고, 매일 수집이 늘린 `coveredThrough`도
   * 새로고침 전까지 차트에 들어오지 않았다 — 003부터 수집이 백그라운드로 돈다.
   */
  loadAll: async () => {
    const { currency, preset } = get();
    set({ loading: true, error: null, collecting: null });
    try {
      const cov = await apiClient.get<{ coverage: CoverageRow[] }>("/api/fx/coverage");
      const row = cov.coverage.find((c) => c.currency === currency) ?? null;
      const from = presetStart(preset, row);
      const presetNotice = presetClampNotice(preset, row);
      const to = row?.coveredThrough ?? from;

      const [latest, daily, series] = await Promise.all([
        apiClient.get<LatestResponse>(`/api/fx/latest?currency=${currency}`),
        apiClient.get<DailyResponse>(
          `/api/fx/daily?currency=${currency}&period=${get().period}`),
        apiClient.get<SeriesResponse | SeriesCollecting>(
          `/api/fx/series?currency=${currency}&from=${from}&to=${to}`,
        ),
      ]);

      // 012 FR-002 — 늦게 온 응답이 그 사이 바뀐 통화·단위의 화면을 덮지 않는다. 통화가 바뀌었으면 새 통화의 다시 받기가 모두 채운다.
      // 단위만 바뀌었으면 표는 기간 전환(`setPeriod`)의 몫이다 — 이 응답의 표는 이전 단위의 것이다.
      if (get().currency !== currency) return;
      const sameUnit = daily.period === get().period;

      const collecting =
        "status" in series && series.status === "collecting"
          ? (series as SeriesCollecting)
          : null;

      set({
        coverage: cov.coverage,
        presetNotice,
        latest,
        ...(sameUnit ? { daily } : {}),
        series: collecting ? null : (series as SeriesResponse),
        collecting,
        // 진입 시 선택 날짜는 가장 최근 고시일이다 (spec Assumptions).
        selectedDate: get().selectedDate ?? latest.date ?? null,
        loading: false,
      });
    } catch (err) {
      if (get().currency !== currency) return;
      set({ error: message(err, "화면을 불러오지 못했습니다."), loading: false });
    }
  },

  /** 통화를 바꾸면 요약·차트·표가 모두 갱신된다 (FR-007). 선택 날짜는 유지한다. */
  setCurrency: async (currency) => {
    const cov = get().coverage.find((c) => c.currency === currency) ?? null;
    const kept = get().selectedDate;
    // 새 통화의 범위 밖이면 그 통화의 최근 고시일로 옮긴다 (contracts/ui-interaction).
    const notice = kept ? checkRange(kept, cov) : null;
    set({
      currency,
      selectedDate: notice ? (cov?.coveredThrough ?? null) : kept,
      notice: null,
      daily: null,
    });
    await get().loadAll();
  },

  /** 기간 프리셋은 차트만 바꾼다. 표는 영향받지 않는다 (갱신 범위 표). */
  setPreset: async (preset) => {
    const { currency } = get();
    const row = get().coverageFor();
    const from = presetStart(preset, row);
    const to = row?.coveredThrough ?? from;
    // FR-019 — 잘렸으면 그 사실을 알린다. 세우지 않으면 EUR에서 40년·50년·전체가
    // 같은 차트인데 이유를 알 수 없다 (SC-012).
    set({
      preset,
      presetNotice: presetClampNotice(preset, row),
      loading: true,
      error: null,
      collecting: null,
    });
    try {
      const series = await apiClient.get<SeriesResponse | SeriesCollecting>(
        `/api/fx/series?currency=${currency}&from=${from}&to=${to}`,
      );
      const collecting =
        "status" in series && series.status === "collecting"
          ? (series as SeriesCollecting)
          : null;
      set({
        series: collecting ? null : (series as SeriesResponse),
        collecting,
        loading: false,
      });
    } catch (err) {
      set({ error: message(err, "차트를 불러오지 못했습니다."), loading: false });
    }
  },

  /**
   * 기간 단위를 바꾸면 표를 새 단위로 다시 받는다 (004 FR-010, FR-011).
   *
   * **선택 날짜는 건드리지 않는다** (FR-019b). 기준일로 옮겨 놓으면 일 단위로
   * 돌아왔을 때 원래 고른 날짜를 잃는다. 강조 대상만 구간으로 찾는다 (research R4-7).
   *
   * 실패해도 단위 선택은 유지한다. 되돌리고 오류만 보이면 사용자는 클릭이 먹지
   * 않은 것으로 여긴다 (002 FR-010에서 같은 판단을 했다).
   */
  setPeriod: async (period) => {
    const { currency } = get();
    // 1겹: 전환 즉시 비운다. 한 프레임도 이전 단위가 남지 않는다 (FR-010, SC-010).
    // `tableEpoch`는 올리지 않는다 — 창을 표의 처음으로 옮기지 않는다(012 FR-001). 표가 떨어진 동안의 높이는 화면이 붙잡는다(`useHeightHold`).
    set({
      period,
      daily: null,
      loadingMore: false,
      loadMoreError: null,
      error: null,
    });
    try {
      const body = await apiClient.get<DailyResponse>(
        `/api/fx/daily?currency=${currency}&period=${period}`,
      );
      // 2겹: 도착한 응답의 단위·통화를 현재 선택과 대조한다 (FR-011, research R4-8, 012 FR-002).
      if (body.period !== get().period || body.currency !== get().currency) return;
      set({ daily: body });
    } catch (err) {
      set({ error: message(err, "표를 불러오지 못했습니다.") });
    }
  },

  /**
   * 선택 날짜 변경은 **대체로 아무것도 다시 받지 않는다**. 예외는 선택 날짜가 표의
   * 현재 표시 범위 밖일 때뿐이다 (FR-022a).
   */
  selectDate: async (date) => {
    const cov = get().coverageFor();
    const notice = checkRange(date, cov);
    if (notice) {
      // **선택 자체는 반영한다.** FR-010은 "값을 반환하지 않는다"를 요구할 뿐 선택을
      // 거절하라고 하지 않았다. 입력값을 이전 날짜로 되돌리면 안내는 범위 밖이라
      // 말하는데 화면은 다른 날짜를 보여줘, 사용자에게는 클릭이 먹지 않은 것처럼 보인다.
      set({ selectedDate: date, notice });
      return;
    }
    set({ selectedDate: date, notice: null });

    const daily = get().daily;
    const inRange =
      daily !== null &&
      daily.rows.length > 0 &&
      date <= daily.rows[0].date &&
      date >= daily.rows[daily.rows.length - 1].date;
    if (inRange) return;

    // 표 밖이면 그 날짜가 첫 행이 되도록 다시 받는다.
    const next = new Date(`${date}T00:00:00Z`);
    next.setUTCDate(next.getUTCDate() + 1);
    try {
      const body = await apiClient.get<DailyResponse>(
        `/api/fx/daily?currency=${get().currency}&period=${get().period}` +
          `&before=${iso(next)}`,
      );
      // 쌓아 둔 행을 **버린다**. 이어 붙이면 30년을 건너뛸 때 그 사이 전부를 한꺼번에
      // 받게 된다 (FR-005a). 스크롤 위치도 처음으로 되돌린다 (FR-005b).
      set({
        daily: body,
        loadMoreError: null,
        tableEpoch: get().tableEpoch + 1,
      });
    } catch (err) {
      set({ error: message(err, "표를 불러오지 못했습니다.") });
    }
  },

  /**
   * 더 과거를 이어 받는다 (FR-026, 004 FR-001). **기존 배열 끝에 덧붙인다** — 전체를
   * 교체하면 보던 위치가 처음으로 튄다 (FR-003, research R4-6).
   *
   * 끝에 도달했거나 이미 불러오는 중이면 아무것도 하지 않는다. 중복 요청은 오류 없이
   * 성공하면서 같은 행을 두 번 그린다 (FR-005, SC-003, SC-004).
   */
  loadMoreDaily: async () => {
    const { currency, daily, loadingMore } = get();
    if (daily === null || !daily.hasMore || loadingMore) return;
    set({ loadingMore: true, loadMoreError: null });
    try {
      const more = await apiClient.get<DailyResponse>(
        `/api/fx/daily?currency=${currency}&period=${get().period}` +
          `&before=${daily.oldestReturned}`,
      );
      // 뒤늦게 도착한 이전 단위의 응답은 버린다 (FR-011). 단위를 대조하지 않으면
      // 주 단위 표에 일 단위 행이 **오류 없이** 이어 붙는다.
      if (more.period !== get().period) {
        set({ loadingMore: false });
        return;
      }
      const current = get().daily;
      set({
        daily: { ...more, rows: [...(current?.rows ?? []), ...more.rows] },
        loadingMore: false,
      });
    } catch (err) {
      // 이미 표시된 행은 그대로 둔다 (FR-004). 조용히 멈추면 사용자는 데이터가
      // 거기서 끝난 것으로 오해한다.
      set({
        loadingMore: false,
        loadMoreError: message(err, "이어서 불러오지 못했습니다."),
      });
    }
  },

  /** 스프레드가 바뀌면 요약과 표만 다시 받는다. 차트는 매매기준율만 그리므로 무관하다. */
  reloadRates: async () => {
    const { currency } = get();
    try {
      const [latest, daily] = await Promise.all([
        apiClient.get<LatestResponse>(`/api/fx/latest?currency=${currency}`),
        apiClient.get<DailyResponse>(
          `/api/fx/daily?currency=${currency}&period=${get().period}`),
      ]);
      set({ latest, daily });
    } catch (err) {
      set({ error: message(err, "값을 새로 계산하지 못했습니다.") });
    }
  },
}));
