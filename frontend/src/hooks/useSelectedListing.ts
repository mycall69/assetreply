"use client";

/**
 * 고른 대상의 상장일 (014 반복 2026-10-10g — FR-034, contracts D13·A11, research R14-27). 주식·코인 검색의 고른 줄이 함께 쓴다.
 *
 * **대상으로 묻는다.** 고른 줄은 등록 뒤에도, 등록이 없는 이력 다시 실행(010) 뒤에도 생긴다 — 등록 응답에만 기대면 다시 실행한 종목은 늘 빈다.
 *
 * **결과가 올 때 다시 묻는다**(`refresh`). 코인의 첫 일봉·종목의 첫 거래일은 실행의 수집이 알게 한다 — 고를 때 한 번만 물으면 처음 고른 코인은
 * 실행 뒤에도 "—"다. 결과가 비는 것(`refresh`가 `undefined`로)은 다시 물을 까닭이 아니다 — 그 대상의 답이 이미 있으면 묻지 않는다.
 *
 * 늦게 온 다른 대상의 답은 버린다(효과 정리). 묻는 동안은 그 대상의 이전 답을 그대로 두고, 처음 묻는 대상이면 아무것도 없다(`loading`) — 빈
 * 칸이 "—"로 깜박이지 않는다. 실패는 `failed`다(표시 전용 — 줄을 그리지 않는다).
 */

import { useEffect, useRef, useState } from "react";
import { fetchListing } from "@/lib/listingApi";
import type { ListingDate } from "@/lib/types";

export type SelectedListing =
  | { state: "loading" }
  | { state: "known"; listing: ListingDate }
  | { state: "unknown" }
  | { state: "failed" };

interface Answer {
  path: string;
  outcome: ListingDate | null | "failed";
}

export function useSelectedListing(path: string | null, refresh?: string): SelectedListing {
  const [answer, setAnswer] = useState<Answer | null>(null);
  // 답을 받은 경로. 효과 안에서만 읽고 쓴다 — 결과가 비는 것으로는 다시 묻지 않는 판정에 쓴다.
  const answered = useRef<string | null>(null);

  useEffect(() => {
    if (path === null) return;
    if (refresh === undefined && answered.current === path) return;
    let live = true;
    fetchListing(path).then(
      (listing) => {
        if (!live) return;
        answered.current = path;
        setAnswer({ path, outcome: listing });
      },
      () => {
        if (!live) return;
        answered.current = path;
        setAnswer({ path, outcome: "failed" });
      },
    );
    return () => {
      live = false;
    };
  }, [path, refresh]);

  if (path === null || answer === null || answer.path !== path) return { state: "loading" };
  if (answer.outcome === "failed") return { state: "failed" };
  if (answer.outcome === null) return { state: "unknown" };
  return { state: "known", listing: answer.outcome };
}
