"use client";

/**
 * 높이 붙잡기 (012 T004) — FR-001, FR-006, research R12-1. 외환·주식·가상자산 화면이 함께 쓴다.
 *
 * 표를 다시 받는 동안 표가 떨어졌다 붙으면 문서가 창보다 짧아져 브라우저가 스크롤을 당긴다(010 R10-16 실측). 그래서 바꾸기 **직전** 높이를 최소
 * 높이로 붙잡는다(010 FR-023 — `app/fx/page.tsx`의 `holdWhile`을 뽑았다).
 *
 * **놓을 때 바닥을 남긴다.** 새 내용이 짧아 창 아래 끝보다 위에서 끝나면, 그냥 놓는 순간 문서가 줄어 창이 끌려 올라간다 — FR-001의 실패 양상 *다른
 * 곳에서 일어남*(월 단위의 짧은 표). 그때는 창 아래 끝까지의 높이를 남긴다. 붙잡았던 높이를 넘기지는 않는다. 다음 붙잡기가 그 바닥을 새 높이로 바꾼다.
 *
 * 내용의 높이는 감싼 요소의 **마지막 자식의 아래 끝**으로 잰다 — 최소 높이가 걸린 요소 자신의 높이는 붙잡은 높이라 내용을 말하지 않는다. 최소 높이를
 * 잠시 걷어 내고 재면 그 순간 브라우저가 스크롤을 당길 수 있다. 잴 수 없으면(0) 지금처럼 놓는다.
 *
 * 빠르게 두 번 바꾸면 늦게 끝난 앞 전환이 뒤 전환의 높이를 놓지 않게 차례를 센다.
 */

import { useCallback, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

export interface HeightHold<T extends HTMLElement> {
  ref: RefObject<T | null>;
  style: CSSProperties | undefined;
  hold: (reload: () => Promise<void>) => void;
}

export function useHeightHold<T extends HTMLElement = HTMLDivElement>(): HeightHold<T> {
  const ref = useRef<T>(null);
  const [reserve, setReserve] = useState<number | null>(null);
  // 끝난 다시 받기의 차례. 바뀌면 새 내용이 그려진 뒤(레이아웃 효과) 바닥을 정한다.
  const [settled, setSettled] = useState(0);
  const turn = useRef(0);
  const held = useRef<number | null>(null);

  const hold = useCallback((reload: () => Promise<void>) => {
    const height = ref.current?.getBoundingClientRect().height ?? 0;
    const mine = ++turn.current;
    held.current = height > 0 ? height : null;
    setReserve(held.current);
    void reload()
      .catch(() => undefined)  // 실패를 알리는 일은 다시 받는 쪽(스토어)이 한다. 여기서는 놓기만 한다
      .finally(() => {
        if (turn.current === mine) setSettled(mine);
      });
  }, []);

  useLayoutEffect(() => {
    if (settled === 0 || settled !== turn.current) return;
    setReserve(floorFor(ref.current, held.current));
  }, [settled]);

  return { ref, style: reserve === null ? undefined : { minHeight: `${reserve}px` }, hold };
}

/**
 * 놓은 뒤 남길 최소 높이. `null`이면 남기지 않는다.
 *
 * 창 아래 끝까지 받치려면 요소가 `창 높이 − 요소 위 끝`만큼 높아야 한다(위 끝은 창 기준 — 창이 요소 안으로 내려가 있으면 음수다).
 */
function floorFor(el: HTMLElement | null, held: number | null): number | null {
  if (el === null || held === null) return null;
  const last = el.lastElementChild;
  if (last === null) return null;
  const top = el.getBoundingClientRect().top;
  const content = last.getBoundingClientRect().bottom - top;
  if (!(content > 0)) return null;
  const needed = Math.min(held, window.innerHeight - top);
  return content >= needed ? null : Math.ceil(needed);
}
