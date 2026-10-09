/**
 * 보드 안내 줄 (013 반복 2026-10-09b T106) — FR-011b, `/speckit-analyze` I1.
 *
 * 예금·가상자산 메뉴 화면과 투자 시뮬레이션 모달이 같은 함수로 안내 줄을 만든다 — 글자는 지금 메뉴 화면의 것과 같다.
 */
import { describe, expect, it } from "vitest";
import { cryptoBoardNotes, depositBoardNotes } from "@/lib/boardNotes";
import { RESULT as CRYPTO } from "./support/cryptoFixtures";
import { RESULT as DEPOSIT } from "./support/depositFixtures";

describe("예금", () => {
  it("투자처·세율·지금 회차", () => {
    expect(depositBoardNotes(DEPOSIT.summary, DEPOSIT.condition, "시중은행")).toEqual([
      "시중은행", "세율 15.4%", "지금 회차 2026-01-15 가입 · 2.84% · 만기 2027-01-15"]);
  });

  it("조건이 없거나 지금 회차가 없으면 그 줄을 뺀다", () => {
    expect(depositBoardNotes({ ...DEPOSIT.summary, currentTerm: null }, null, "상호금융")).toEqual(["상호금융"]);
  });
});

describe("가상자산", () => {
  it("매수일·수수료", () => {
    expect(cryptoBoardNotes(CRYPTO.summary, CRYPTO.condition)).toEqual(["매수일 2020-01-01", "수수료 0.10%"]);
  });

  it("조건이 없으면 매수일만", () => {
    expect(cryptoBoardNotes(CRYPTO.summary, null)).toEqual(["매수일 2020-01-01"]);
  });
});
