/**
 * 늦게 온 응답 버리기 (T042) — 006 FR-029a, research R6-12.
 *
 * 요청마다 번호를 붙이고, 응답의 번호가 최신이 아니면 버린다. 005의 검색 칸은
 * 입력 대기 타이머만 있어 **늦게 온 이전 검색의 응답이 최신 결과를 덮을 수
 * 있었다** — 사용자는 지금 친 검색어의 결과로 읽고 엉뚱한 종목을 고른다.
 *
 * 로컬·외부 검색은 **번호를 따로 가진다.** 하나를 같이 쓰면 일본 검색이 느릴
 * 때마다 로컬 결과가 낡은 것으로 버려진다.
 */

export interface RequestSequence {
  /** 새 요청의 번호. 이전 번호는 모두 낡는다. */
  next(): number;
  isLatest(id: number): boolean;
  /** 진행 중인 응답을 모두 낡게 한다 — 검색어를 지웠을 때. */
  invalidate(): void;
}

export function createSequence(): RequestSequence {
  let latest = 0;
  return {
    next: () => {
      latest += 1;
      return latest;
    },
    isLatest: (id) => id === latest,
    invalidate: () => {
      latest += 1;
    },
  };
}
