/**
 * 단지의 Npay 부동산 단지 화면 주소 (010 반복 3, T066) — FR-029, data-model 8.2, contracts/rest-api 반복 3.
 *
 * 백엔드가 공개되지 않은 단지 자동완성으로 번호를 한 번 찾아 저장한다(헌법 원칙 II 이탈). 화면은 **단지마다 한 번만** 묻는다 —
 * 보드와 이력 행에 같은 단지가 여럿이어도, 다시 그려져도 같은 답을 쓴다. 못 찾음·실패·요청 오류는 `null`이고 링크는 네이버 검색
 * (FR-026)으로 남는다 — 같은 쪽 안에서는 다시 묻지 않는다(출처를 거듭 부르지 않게).
 */

import { useEffect, useState } from "react";
import { apiClient } from "./apiClient";

interface NaverComplexAnswer {
  complexId: number;
  status: "found" | "not_found" | "failed";
  url: string | null;
  reason: string | null;
}

const asked = new Map<number, Promise<string | null>>();

/** 단지 번호 경로의 답 — Npay 부동산 단지 화면 주소, 모르면 `null`. 단지마다 한 번만 부른다. */
export function askNaverComplex(complexId: number): Promise<string | null> {
  const known = asked.get(complexId);
  if (known !== undefined) return known;
  const pending = apiClient
    .get<NaverComplexAnswer>(`/api/realestate/complexes/${complexId}/naver`)
    .then((body) => (body.status === "found" && body.url ? body.url : null))
    .catch(() => null);
  asked.set(complexId, pending);
  return pending;
}

/** 단지의 Npay 부동산 단지 화면 주소. 답이 오기 전·모를 때는 `null`. */
export function useNaverComplexHref(complexId: number): string | null {
  const [href, setHref] = useState<{ id: number; url: string | null } | null>(null);
  useEffect(() => {
    let alive = true;
    void askNaverComplex(complexId).then((url) => {
      if (alive) setHref({ id: complexId, url });
    });
    return () => {
      alive = false;
    };
  }, [complexId]);
  return href !== null && href.id === complexId ? href.url : null;
}

/** 테스트 사이에 기억을 비운다. */
export function resetNaverComplexLinks(): void {
  asked.clear();
}
