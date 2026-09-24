"use client";

/**
 * 통화 카드 (T046) — contracts/ui-wireframes.md W3.
 *
 * 카드 오른쪽 위 배지와 막대 아래 한 줄이 상태를 말한다.
 *
 * **"지금 하실 일은 없습니다"가 FR-006a의 요구다.** 경고만 띄우고 설명이 없으면
 * 사용자는 자기가 뭔가 해야 한다고 오해한다. 회수는 시스템이 하는 일이다.
 *
 * `[ 이어받기 ]`와 `[ 수집 시작 ]`은 **같은 동작**이다. 문구만 상황에 맞춘다 — 이미
 * 일부 받은 통화에 "수집 시작"이라고 쓰면 처음부터 다시 받는다는 오해를 준다.
 */

import { CurrencyTimeline } from "./CurrencyTimeline";
import type { CurrencyCode, TimelineSnapshot } from "@/lib/types";

const NAMES: Record<CurrencyCode, string> = {
  USD: "미국 달러",
  JPY: "일본 엔",
  EUR: "유로",
};

interface Badge {
  text: string;
  tone: string;
}

function badgeFor(snapshot: TimelineSnapshot): Badge {
  const active = snapshot.activeJob;
  if (active) {
    if (active.state === "stalled") {
      return { text: "⚠ 응답 없음", tone: "bg-amber-100 text-amber-800" };
    }
    if (active.state === "awaiting_reclaim") {
      return { text: "⚠ 회수 대기", tone: "bg-amber-100 text-amber-800" };
    }
    return { text: "진행 중", tone: "bg-sky-100 text-sky-800" };
  }
  if (!snapshot.coveredThrough) {
    return { text: "수집 이력 없음", tone: "bg-gray-100 text-gray-600" };
  }
  if (snapshot.coveredThrough >= snapshot.targetTo) {
    return { text: "완료", tone: "bg-green-100 text-green-800" };
  }
  return { text: "부분 완료", tone: "bg-gray-100 text-gray-700" };
}

function detailFor(snapshot: TimelineSnapshot): string {
  const active = snapshot.activeJob;
  if (active) {
    if (active.state === "stalled") {
      return "60초 이상 진전이 없습니다. 회수를 기다리는 중이며 지금 하실 일은 없습니다.";
    }
    if (active.state === "awaiting_reclaim") {
      return "곧 부분 완료로 정리됩니다. 지금 하실 일은 없습니다.";
    }
    const resumed = active.rangeStart !== snapshot.targetFrom;
    const progress = `${active.chunksDone}/${active.chunksTotal} 구간`;
    return resumed
      ? `${active.rangeStart}부터 이어받는 중 · ${progress}`
      : `${progress} 수집 중`;
  }
  if (!snapshot.coveredThrough) return "아직 수집하지 않았습니다.";
  if (snapshot.coveredThrough >= snapshot.targetTo) {
    return `${snapshot.coveredThrough}까지 수집 완료`;
  }
  return `${snapshot.coveredThrough}까지 수집`;
}

/** 조작 문구. 이미 일부 받았으면 "이어받기"다. */
function actionLabel(snapshot: TimelineSnapshot): string {
  if (!snapshot.coveredThrough) return "수집 시작";
  if (snapshot.coveredThrough >= snapshot.targetTo) return "다시 확인";
  return "이어받기";
}

export function CurrencyCard({
  snapshot,
  onStart,
}: {
  snapshot: TimelineSnapshot;
  onStart: () => void;
}) {
  const badge = badgeFor(snapshot);
  // 진행 중이 아닐 때 진행 표시를 내보내지 않는다 (FR-016).
  const running = snapshot.activeJob !== undefined;
  const blocked = snapshot.busyWith !== null;

  return (
    <section className="space-y-3 rounded-lg border border-gray-200 p-4">
      <header className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-900">
          {snapshot.currency} · {NAMES[snapshot.currency]}
        </h3>
        <span className={`rounded px-2 py-0.5 text-xs ${badge.tone}`}>
          {badge.text}
        </span>
      </header>

      <CurrencyTimeline snapshot={snapshot} />

      <div className="flex items-center justify-between gap-4">
        <p className="text-xs text-gray-600">{detailFor(snapshot)}</p>
        {!running && (
          <button
            type="button"
            onClick={onStart}
            disabled={blocked}
            // 막힌 이유가 버튼과 함께 읽혀야 한다. 비활성 상태만으로는 알 수 없다.
            aria-describedby={blocked ? "collection-busy" : undefined}
            className="shrink-0 rounded border border-gray-300 px-3 py-1 text-xs text-gray-800 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {actionLabel(snapshot)}
          </button>
        )}
      </div>

      {blocked && (
        <p id="collection-busy" className="text-xs text-amber-700">
          {snapshot.busyWith}를 수집하는 중입니다. 끝나면 {snapshot.currency}를
          시작할 수 있습니다.
        </p>
      )}
    </section>
  );
}
