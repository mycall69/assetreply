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

// 이 환경의 jsdom은 `localStorage`를 **멤버가 없는 빈 객체**로 노출한다. 005의 이력
// 보관(FR-037)은 저장소 동작 자체가 요구사항이라 최소 구현을 둔다.
//
// 메서드를 인스턴스가 아니라 `Storage.prototype`에 두는 이유가 있다 — 테스트가 그
// 자리에 실패를 주입해 **보관 한계에 닿았을 때 알리는지**를 검증한다 (research R5-10).
// 인스턴스에 직접 두면 스파이가 걸리지 않아 그 경로가 검증되지 않은 채 통과한다.
if (typeof Storage === "function" && typeof localStorage?.clear !== "function") {
  const data = new Map<string, string>();
  Object.assign(Storage.prototype, {
    getItem(key: string): string | null {
      return data.has(key) ? (data.get(key) as string) : null;
    },
    setItem(key: string, value: string): void {
      data.set(key, String(value));
    },
    removeItem(key: string): void {
      data.delete(key);
    },
    clear(): void {
      data.clear();
    },
    key(index: number): string | null {
      return [...data.keys()][index] ?? null;
    },
  });
  Object.defineProperty(globalThis, "localStorage", {
    configurable: true,
    value: Object.create(Storage.prototype) as Storage,
  });
}

// 012 T043 — `/api/history` 대역(research R12-12). 이력은 시뮬레이션과 실패 영역이 다르고, 화면은 공통 요청 함수로 `fetch`를 부른다. 이력이 주제가
// 아닌 테스트는 빈 이력과 성공하는 저장을 본다. 그 밖의 경로는 원래 `fetch`로 넘긴다(지금과 같다). 테스트마다 비운다.
import { beforeEach } from "vitest";
import { handleHistory, resetHistoryStub } from "./support/historyStub";
import { handleSavedComparisons, resetSavedComparisonStub } from "./support/savedComparisonStub";

const originalFetch = globalThis.fetch;
globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  const answered = await handleHistory(input, init);
  return answered ?? originalFetch(input, init);
};
beforeEach(() => {
  resetHistoryStub();
});

// 013 T060 — `/api/comparison/saved` 대역(이력 대역과 같은 틀). 이력 대역을 감싼 `fetch`를 한 겹 더 감싼다 — 저장한 비교가 주제가 아닌 테스트는
// 빈 목록과 성공하는 저장을 본다.
const historyFetch = globalThis.fetch;
globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> =>
  (await handleSavedComparisons(input, init)) ?? historyFetch(input, init);
beforeEach(() => {
  resetSavedComparisonStub();
});
