"use client";

/**
 * 수집 중 안내 (T095) — 005 FR-047, FR-049, ui-wireframes W7. 006 T055에서 환율 줄(W4)과
 * 수집으로 채울 수 없는 구간(W4a)을 더했다. 009 T026에서 부동산 실거래의 202·진행(받은 달 / 받을 달)을
 * 더했다 — 주어·단위는 008의 선택 속성이고, 받을 구간 대신 달 수만 안다.
 *
 * **부분 결과를 보여주지 않는다**(FR-049). 받은 만큼만 계산한 수익률은 값이 멀쩡해
 * 보이지만 틀린 값이며, 사용자는 그것을 최종 결과로 읽는다. 그래서 숫자 대신 **진행과
 * 기다릴 이유**를 보인다. 006 — 주식 시세와 환율이 **둘 다 끝나기 전에는** 결과가 없다
 * (FR-045).
 */

import type { CryptoProgressSnapshot } from "@/lib/cryptoProgressStream";
import type { DepositProgressSnapshot } from "@/lib/depositProgressStream";
import type { RealEstateProgressSnapshot } from "@/lib/realEstateProgressStream";
import type { StockProgressSnapshot } from "@/lib/stockProgressStream";
import type {
  CryptoCollecting,
  DepositCollecting,
  FxCollecting,
  FxNotAvailableBefore,
  RealEstateTradeCollecting,
  SimulationCollecting,
} from "@/lib/types";

/**
 * 수집 중 본문 — 주식(005·006)·가상자산(007)·예금(008)·부동산 실거래(009)의 202. 이 안내는 대상(종목·코인·투자처·시·군·구)의
 * 식별을 쓰지 않는다.
 */
export type CollectingLike = SimulationCollecting | CryptoCollecting | DepositCollecting | RealEstateTradeCollecting;

/**
 * 진행 — 받은 날 / 받을 날(006 FR-045a). 예금(008)은 받은 달 / 받을 달이다 — 금리가 월별이다. 부동산(009)은 종류와 상관없이
 * `done`·`total`이고 실거래는 달이다.
 */
export type ProgressLike =
  | StockProgressSnapshot | CryptoProgressSnapshot | DepositProgressSnapshot | RealEstateProgressSnapshot;

/** 받은 양 / 받을 양. 예금·부동산 실거래는 달, 나머지는 날이다. */
function amounts(progress: ProgressLike | null): { done: number; total: number } {
  if (progress === null) return { done: 0, total: 0 };
  if ("monthsTotal" in progress) return { done: progress.monthsDone, total: progress.monthsTotal };
  if ("daysTotal" in progress) return { done: progress.daysDone, total: progress.daysTotal };
  return { done: progress.done, total: progress.total };
}

/** 환율 줄 (W4). `waiting`은 다른 통화의 수집이 끝나야 시작한다 (FR-046). */
function fxLine(fx: FxCollecting): string {
  switch (fx.state) {
    case "queued":
      return `${fx.currency} 환율: 대기열에 넣었습니다`;
    case "collecting":
      return `${fx.currency} 환율을 받고 있습니다`;
    case "waiting":
      return `${fx.currency} 환율: ${fx.busyWith ?? "다른 통화"} 수집이 끝나면 시작합니다`;
  }
}

export function CollectingNotice({
  collecting,
  stockName,
  progress,
  subject = "시세",
  unit = "일",
  doneNote,
}: {
  collecting: CollectingLike;
  /** 받고 있는 대상의 이름 — 종목명이나 코인 이름(007), 투자처 이름(008). */
  stockName: string;
  progress: ProgressLike | null;
  /** 받고 있는 것 — 시세, 예금은 금리(008). */
  subject?: string;
  /** 진행의 단위 — 일, 예금은 개월(008). */
  unit?: string;
  /** 끝나면 무엇이 달라지는지 — 기본은 결과가 표시된다는 말이다. 부동산 단지 목록(009)은 단지가 더해진다. */
  doneNote?: string;
}) {
  // 006 FR-045a — 받은 날 / 받을 날(달력 일수). "3 / 4 구간"은 숫자가 작아 얼마나 남았는지
  // 가늠하기 어렵다. 출처에 2년치씩 요청하므로 숫자는 구간마다 늘어난다.
  const { done, total } = amounts(progress);
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;
  const stockCollecting = collecting.jobId !== undefined;
  const fx = "fx" in collecting ? collecting.fx : undefined;
  // 부동산 실거래(009)는 받을 구간 대신 받을 달 수만 안다 — 구간 줄을 그리지 않는다.
  const range = "missingFrom" in collecting && collecting.missingFrom !== undefined
    ? { from: collecting.missingFrom, through: collecting.missingThrough } : null;

  return (
    <section
      role="status"
      className="space-y-3 rounded-lg border border-gray-200 px-4 py-5 text-sm text-gray-700"
    >
      {stockCollecting && (
        <>
          <p className="font-medium">{stockName}의 {subject}를 받고 있습니다</p>

          {total > 0 ? (
            <div className="space-y-1">
              <div
                role="progressbar"
                aria-valuenow={done}
                aria-valuemin={0}
                aria-valuemax={total}
                aria-label={`${stockName} 수집 진행`}
                className="h-2 w-full overflow-hidden rounded bg-gray-100"
              >
                <div className="h-full bg-gray-700" style={{ width: `${percent}%` }} />
              </div>
              <p className="text-xs tabular-nums text-gray-500">
                {done.toLocaleString("ko-KR")} / {total.toLocaleString("ko-KR")}{unit}
              </p>
            </div>
          ) : (
            // 0/0을 보이면 멈춘 것처럼 읽힌다. 아직 시작 단계라는 사실을 말한다.
            <p className="text-xs text-gray-500">시작하는 중…</p>
          )}

          {range !== null && (
            <p className="text-xs tabular-nums text-gray-500">
              받을 구간: {range.from} ~ {range.through}
            </p>
          )}
        </>
      )}

      {fx !== undefined && (
        <div className="space-y-1">
          <p className={stockCollecting ? "" : "font-medium"}>{fxLine(fx)}</p>
          <p className="text-xs tabular-nums text-gray-500">
            받을 환율 구간: {fx.missingFrom} ~ {fx.missingThrough}
          </p>
        </div>
      )}

      <p className="text-xs text-gray-500">
        {doneNote ?? (stockCollecting && fx !== undefined
          ? "둘 다 끝나면 결과가 표시됩니다."
          : "완료되면 결과가 표시됩니다.")}
      </p>
    </section>
  );
}

/**
 * 수집으로 채울 수 없는 구간 (W4a, 006 FR-043a).
 *
 * **두 문구를 섞지 않는다.** 설정 밖(`before_probe_start`)은 풀 수 있는 제약이라 할 일(설정
 * 변경)을 함께 말한다. 옮기기는 **버튼을 눌러야** 바뀐다 — 몰래 옮기지 않는다(005 FR-005).
 */
export function FxUnavailableNotice({
  blocked,
  onMove,
}: {
  blocked: FxNotAvailableBefore;
  onMove: (start: string) => void;
}) {
  const month = blocked.availableFrom.slice(0, 7);
  return (
    <div
      role="alert"
      className="space-y-1 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900"
    >
      <p>⚠ {blocked.message}</p>
      {blocked.reason === "before_probe_start" && (
        <p className="text-xs">
          설정(ECOS_PROBE_START_{blocked.currency})을 바꾸면 받을 수 있습니다. 또는
        </p>
      )}
      <p className="text-xs">
        시작일을 {month} 이후로 옮기세요.{" "}
        <button
          type="button"
          onClick={() => onMove(blocked.availableFrom)}
          className="ml-1 rounded border border-amber-300 bg-white px-2 py-0.5"
        >
          {month}로 옮기기
        </button>
      </p>
    </div>
  );
}
