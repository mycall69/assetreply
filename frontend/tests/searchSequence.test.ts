/**
 * 늦게 온 응답 버리기 (T026) — 006 FR-029a, research R6-12.
 *
 * 005의 검색 칸은 입력 대기 타이머만 있고 **응답 순서를 확인하지 않았다** — 늦게 온 이전
 * 검색의 응답이 최신 결과를 덮을 수 있었다. 사용자는 지금 친 검색어의 결과로 읽고 엉뚱한
 * 종목을 고른다.
 */
import { describe, expect, it } from "vitest";
import { createSequence } from "@/lib/searchSequence";

describe("요청 번호", () => {
  it("요청마다 커지는 번호를 준다", () => {
    const seq = createSequence();
    const a = seq.next();
    const b = seq.next();
    expect(b).toBeGreaterThan(a);
  });

  it("최신 번호만 최신이다", () => {
    const seq = createSequence();
    const first = seq.next();
    expect(seq.isLatest(first)).toBe(true);
    const second = seq.next();
    expect(seq.isLatest(first)).toBe(false);
    expect(seq.isLatest(second)).toBe(true);
  });

  it("뒤늦게 온 응답이 먼저 온 최신 응답을 덮지 않는다", () => {
    const seq = createSequence();
    const shown: string[] = [];
    const slow = seq.next();       // "삼"
    const fast = seq.next();       // "삼성전자"
    const deliver = (id: number, value: string) => {
      if (seq.isLatest(id)) shown.push(value);
    };
    deliver(fast, "삼성전자의 결과");
    deliver(slow, "삼의 결과");
    expect(shown).toEqual(["삼성전자의 결과"]);
  });

  it("로컬과 외부는 번호를 따로 가진다", () => {
    // 한쪽 요청이 다른 쪽의 응답을 낡은 것으로 만들면, 일본 검색이 느릴 때마다 로컬 결과가 버려진다.
    const localSeq = createSequence();
    const externalSeq = createSequence();
    const l = localSeq.next();
    externalSeq.next();
    externalSeq.next();
    expect(localSeq.isLatest(l)).toBe(true);
  });

  it("무효화하면 진행 중인 응답이 모두 낡는다", () => {
    // 검색어를 지우면 그 전에 나간 요청의 응답이 빈 칸을 다시 채우면 안 된다.
    const seq = createSequence();
    const id = seq.next();
    seq.invalidate();
    expect(seq.isLatest(id)).toBe(false);
  });
});
