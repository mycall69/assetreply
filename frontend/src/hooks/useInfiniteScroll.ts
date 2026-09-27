"use client";

/**
 * 이어 보기 촉발 (T014) — 004 FR-001a, FR-005.
 *
 * **스크롤 이벤트가 아니라 가시성을 신호로 삼는다.** 표가 화면보다 짧으면 스크롤이
 * 일어나지 않으므로, 스크롤을 기다리는 구현은 이어 보기를 **시도조차 하지 않는다**.
 * 실패 신호가 없어 사용자에게는 데이터가 그것뿐인 것과 구별되지 않는다 (FR-001a).
 *
 * `enabled`가 거짓인 동안에는 부르지 않는다 — 이미 불러오는 중이거나 끝에 도달한
 * 상태다. 중복 요청은 오류 없이 성공하면서 같은 행을 두 번 그린다 (FR-005, SC-004).
 *
 * 감시 지점이 계속 보이는 채로 `enabled`가 거짓에서 참으로 돌아오면 **다시 부른다**.
 * 한 번 받아도 표가 여전히 화면보다 짧을 수 있기 때문이다 (SC-001b).
 */

import { useCallback, useEffect, useRef, useState } from "react";

export function useInfiniteScroll(
  onLoadMore: () => void,
  enabled: boolean,
): (node: HTMLElement | null) => void {
  const [visible, setVisible] = useState(false);
  const observer = useRef<IntersectionObserver | null>(null);

  // 최신 콜백을 참조로 들고 있어야 관찰자를 다시 만들지 않는다. 다시 만들면 관찰이
  // 끊겼다 이어지며 그 사이의 가시성 변화를 놓친다.
  //
  // 호출부가 인라인 화살표를 넘기면 매 렌더마다 콜백의 정체가 바뀐다. 그것을 아래
  // 효과의 의존성에 넣으면 **보이는 동안 매 렌더마다 다시 부른다** — 오류 없이
  // 같은 요청이 반복된다. 그래서 참조에 담아 의존성에서 뺀다.
  //
  // 이 갱신이 아래 촉발 효과보다 **먼저 선언되어야** 한다. 효과는 선언 순서대로
  // 실행되므로, 뒤에 두면 그 커밋에서 낡은 콜백이 불린다.
  const latest = useRef(onLoadMore);
  useEffect(() => {
    latest.current = onLoadMore;
  }, [onLoadMore]);

  const ref = useCallback((node: HTMLElement | null) => {
    observer.current?.disconnect();
    observer.current = null;
    if (node === null) {
      setVisible(false);
      return;
    }
    const io = new IntersectionObserver((entries) => {
      setVisible(entries.some((e) => e.isIntersecting));
    });
    io.observe(node);
    observer.current = io;
  }, []);

  useEffect(() => {
    if (visible && enabled) latest.current();
  }, [visible, enabled]);

  useEffect(() => () => observer.current?.disconnect(), []);

  return ref;
}
