// Vitest 전역 설정 — React Testing Library 매처 등록
import "@testing-library/jest-dom/vitest";

// jsdom에는 `IntersectionObserver`가 없다. 이것을 쓰는 컴포넌트가 다른 테스트에서
// 생성자 오류로 죽지 않도록 최소 스텁을 둔다. 가시성 동작 자체는
// `useInfiniteScroll.test.ts`가 관찰자를 직접 붙잡아 검증한다.
class NoopIntersectionObserver implements IntersectionObserver {
  readonly root = null;
  readonly rootMargin = "";
  readonly thresholds: ReadonlyArray<number> = [];
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
  takeRecords(): IntersectionObserverEntry[] {
    return [];
  }
}

if (!("IntersectionObserver" in globalThis)) {
  globalThis.IntersectionObserver = NoopIntersectionObserver;
}
