"use client";

/**
 * 확대 구간의 일 단위 자료 (014 반복 2026-10-11c) — spec FR-038, data-model 16, research R14-31.
 *
 * - 확대가 끝나면(`onZoom`) 그 구간을 받는다 — 받는 함수(`load`)가 없으면 받지 않는다(예금·부동산·이미 일봉 전부인 그래프). 받은 구간이 새 구간을
 *   덮으면 다시 받지 않는다(확대 안의 재확대)
 * - 받은 자료는 **그것을 받은 바탕 자료·테마에만** 쓴다 — 다시 실행·대상·테마가 바뀌면 그리기에서 빠진다(늦게 온 응답도 같은 까닭으로 버린다).
 *   [리셋](`onReset`)이면 버린다. 차례 번호로 늦은 응답(리셋 뒤·다른 구간을 고른 뒤)을 버린다
 * - 받는 동안 `loading`, 실패(202 포함)면 `failed` — 확대는 그대로이고 원래 점으로 보인다
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { DetailNote } from "@/components/ChartZoomControls";
import { covers } from "@/lib/chartDetail";
import type { ZoomRange } from "@/lib/chartZoom";

interface Received<D> {
  base: unknown;
  theme: string;
  range: ZoomRange;
  data: D;
}

interface Note {
  base: unknown;
  theme: string;
  value: Exclude<DetailNote, null>;
}

export function useZoomDetail<D>(base: unknown, theme: string, load: ((range: ZoomRange) => Promise<D>) | undefined) {
  const [received, setReceived] = useState<Received<D> | null>(null);
  const [note, setNote] = useState<Note | null>(null);
  const seq = useRef(0);
  const active = received !== null && received.base === base && received.theme === theme ? received : null;
  const now = useRef({ base, theme, load, active });
  useEffect(() => {
    now.current = { base, theme, load, active };
  });

  const onZoom = useCallback((range: ZoomRange) => {
    const { base: from, theme: tone, load: fetchDetail, active: shown } = now.current;
    if (fetchDetail === undefined) return;
    if (shown !== null && covers(shown.range, range)) return;
    const id = ++seq.current;
    setNote({ base: from, theme: tone, value: "loading" });
    fetchDetail(range).then(
      (data) => {
        if (seq.current !== id) return;
        setReceived({ base: from, theme: tone, range, data });
        setNote(null);
      },
      () => {
        if (seq.current !== id) return;
        setNote({ base: from, theme: tone, value: "failed" });
      },
    );
  }, []);

  const onReset = useCallback(() => {
    seq.current += 1;
    setReceived(null);
    setNote(null);
  }, []);

  return {
    /** 지금 그리기에 쓰는 받은 자료(받은 그대로의 객체 — 그리기 효과의 의존성으로 쓴다) — 없으면 `null`(원래 점). */
    detail: active as { range: ZoomRange; data: D } | null,
    note: note !== null && note.base === base && note.theme === theme ? note.value : null,
    onZoom,
    onReset,
  };
}
