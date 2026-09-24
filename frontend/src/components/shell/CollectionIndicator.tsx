"use client";

/**
 * 수집 진행 표시기 (T014, 003 T073) — FR-049, FR-030, ui-wireframes W7.
 *
 * 사이드바 메뉴에 "수집 현황"이 없으므로 이 표시기가 수집 현황 화면으로 가는 **유일한
 * 진입점**이다 (002 research R2-10).
 *
 * **그래서 진행 여부와 무관하게 항상 보여야 한다** (003 FR-030, research R3-12).
 * 진행 중일 때만 나타나면 한 번도 수집하지 않은 상태에서 시작할 방법이 없어 고리가
 * 닫힌다 — 수집을 시작하려면 그 화면에 가야 하는데, 그 화면에 가려면 수집이 돌고
 * 있어야 한다.
 */

import Link from "next/link";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/apiClient";
import type { JobRow } from "@/lib/types";

/** 진행 중인 수집이 있는지 주기적으로 확인한다. */
export function CollectionIndicator({ pollMs = 10_000 }: { pollMs?: number }) {
  const [running, setRunning] = useState<string[]>([]);

  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const body = await apiClient.get<{ jobs: JobRow[] }>(
          "/api/fx/jobs?status=running&limit=5",
        );
        if (alive) setRunning(body.jobs.map((j) => j.currency));
      } catch {
        // 조회 실패는 "진행 중인 수집 없음"으로 다룬다. **링크 자체는 남는다** —
        // 유일한 진입점이 서버 불안정으로 사라지면 기능 전체가 도달 불가능해진다.
        if (alive) setRunning([]);
      }
    };
    void check();
    const id = setInterval(() => void check(), pollMs);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [pollMs]);

  const idle = running.length === 0;

  return (
    <Link
      href="/fx/collection"
      className={
        idle
          ? "flex items-center gap-2 rounded px-2 py-1 text-xs text-gray-600 hover:bg-gray-100"
          : "flex items-center gap-2 rounded px-2 py-1 text-xs text-amber-700 hover:bg-amber-50"
      }
    >
      {idle ? (
        // 아이콘을 두는 이유는 텍스트만 있으면 사용자가 **상태 표시로 오해해 클릭을
        // 시도하지 않기** 때문이다. 누를 수 있다는 사실이 형태로 드러나야 한다.
        <span aria-hidden>⟳</span>
      ) : (
        <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-amber-500" />
      )}
      {idle ? "수집 현황" : `수집 중 (${running.join(", ")})`}
    </Link>
  );
}
