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
  SeriesCollecting,
  SeriesResponse,
} from "@/lib/types";

export type Preset = "1m" | "6m" | "1y" | "5y" | "10y" | "all";

/**
 * 기간 프리셋. 일 단위 데이터에서 하루·일주일 구간은 표시할 점이 너무 적어 추이로서
 * 의미가 없으므로 제외했다 (spec Assumptions).
 */
export const PRESETS: ReadonlyArray<{ key: Preset; label: string }> = [
  { key: "1m", label: "1개월" },
  { key: "6m", label: "6개월" },
  { key: "1y", label: "1년" },
  { key: "5y", label: "5년" },
  { key: "10y", label: "10년" },
  { key: "all", label: "전체" },
];

function yesterday(): Date {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  return d;
}

const iso = (d: Date): string => d.toISOString().slice(0, 10);

/**
 * 프리셋 → 시작일. "전체"는 통화마다 다르므로 여기서 정할 수 없다(FR-002).
 * 커버리지에서 받은 값을 호출부가 채운다.
 */
export function presetStart(preset: Preset, coverage: CoverageRow | null): string {
  const end = yesterday();
  const start = new Date(end);
  if (preset === "1m") start.setMonth(start.getMonth() - 1);
  else if (preset === "6m") start.setMonth(start.getMonth() - 6);
  else if (preset === "1y") start.setFullYear(start.getFullYear() - 1);
  else if (preset === "5y") start.setFullYear(start.getFullYear() - 5);
  else if (preset === "10y") start.setFullYear(start.getFullYear() - 10);
  else return coverage?.firstAvailableDate ?? coverage?.coveredFrom ?? iso(start);

  // 프리셋이 요구하는 구간이 축적 시작일보다 이르면 실제 범위만 쓴다 (FR-019).
  const floor = coverage?.firstAvailableDate ?? coverage?.coveredFrom;
  const wanted = iso(start);
  return floor && wanted < floor ? floor : wanted;
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
  coverage: CoverageRow[];
  latest: LatestResponse | null;
  daily: DailyResponse | null;
  series: SeriesResponse | null;
  collecting: SeriesCollecting | null;
  notice: RangeNotice | null;
  loading: boolean;
  error: string | null;

  coverageFor: (currency?: CurrencyCode) => CoverageRow | null;
  setCurrency: (c: CurrencyCode) => Promise<void>;
  setPreset: (p: Preset) => Promise<void>;
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
  coverage: [],
  latest: null,
  daily: null,
  series: null,
  collecting: null,
  notice: null,
  loading: false,
  error: null,

  coverageFor: (currency) => {
    const code = currency ?? get().currency;
    return get().coverage.find((c) => c.currency === code) ?? null;
  },

  /**
   * 진입 시 네 번의 병렬 호출 (research R2-6). 커버리지는 세 통화를 한 번에 반환하므로
   * 통화를 바꿔도 다시 받지 않는다.
   */
  loadAll: async () => {
    const { currency, preset, coverage } = get();
    set({ loading: true, error: null, collecting: null });
    try {
      const covPromise =
        coverage.length > 0
          ? Promise.resolve({ coverage })
          : apiClient.get<{ coverage: CoverageRow[] }>("/api/fx/coverage");
      const cov = await covPromise;
      const row = cov.coverage.find((c) => c.currency === currency) ?? null;
      const from = presetStart(preset, row);
      const to = row?.coveredThrough ?? from;

      const [latest, daily, series] = await Promise.all([
        apiClient.get<LatestResponse>(`/api/fx/latest?currency=${currency}`),
        apiClient.get<DailyResponse>(`/api/fx/daily?currency=${currency}`),
        apiClient.get<SeriesResponse | SeriesCollecting>(
          `/api/fx/series?currency=${currency}&from=${from}&to=${to}`,
        ),
      ]);

      const collecting =
        "status" in series && series.status === "collecting"
          ? (series as SeriesCollecting)
          : null;

      set({
        coverage: cov.coverage,
        latest,
        daily,
        series: collecting ? null : (series as SeriesResponse),
        collecting,
        // 진입 시 선택 날짜는 가장 최근 고시일이다 (spec Assumptions).
        selectedDate: get().selectedDate ?? latest.date ?? null,
        loading: false,
      });
    } catch (err) {
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
    set({ preset, loading: true, error: null, collecting: null });
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
   * 선택 날짜 변경은 **대체로 아무것도 다시 받지 않는다**. 예외는 선택 날짜가 표의
   * 현재 표시 범위 밖일 때뿐이다 (FR-022a).
   */
  selectDate: async (date) => {
    const cov = get().coverageFor();
    const notice = checkRange(date, cov);
    if (notice) {
      set({ notice });
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
        `/api/fx/daily?currency=${get().currency}&before=${iso(next)}`,
      );
      set({ daily: body });
    } catch (err) {
      set({ error: message(err, "표를 불러오지 못했습니다.") });
    }
  },

  /** 더 과거를 이어 받는다 (FR-026). 기존 행 뒤에 붙인다. */
  loadMoreDaily: async () => {
    const { currency, daily } = get();
    if (daily === null || !daily.hasMore) return;
    try {
      const more = await apiClient.get<DailyResponse>(
        `/api/fx/daily?currency=${currency}&before=${daily.oldestReturned}`,
      );
      set({ daily: { ...more, rows: [...daily.rows, ...more.rows] } });
    } catch (err) {
      set({ error: message(err, "이어서 불러오지 못했습니다.") });
    }
  },

  /** 스프레드가 바뀌면 요약과 표만 다시 받는다. 차트는 매매기준율만 그리므로 무관하다. */
  reloadRates: async () => {
    const { currency } = get();
    try {
      const [latest, daily] = await Promise.all([
        apiClient.get<LatestResponse>(`/api/fx/latest?currency=${currency}`),
        apiClient.get<DailyResponse>(`/api/fx/daily?currency=${currency}`),
      ]);
      set({ latest, daily });
    } catch (err) {
      set({ error: message(err, "값을 새로 계산하지 못했습니다.") });
    }
  },
}));
