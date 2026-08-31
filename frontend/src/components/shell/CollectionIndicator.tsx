"use client";

/**
 * 수집 진행 표시기 (T014) — FR-049, contracts/ui-wireframes.md W1.
 *
 * 진행 중일 때만 나타난다. 사이드바 메뉴에 "수집 현황"이 없으므로(FR-002의 8개 항목)
 * 이 표시기가 수집 현황 화면으로 가는 유일한 진입점이다 (research R2-10).
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
        // 표시기는 부가 정보다. 실패해도 화면을 방해하지 않는다.
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

  if (running.length === 0) return null;

  return (
    <Link
      href="/fx/collection"
      className="flex items-center gap-2 rounded px-2 py-1 text-xs text-amber-700 hover:bg-amber-50"
    >
      <span aria-hidden className="inline-block h-2 w-2 rounded-full bg-amber-500" />
      수집 중 ({running.join(", ")})
    </Link>
  );
}
