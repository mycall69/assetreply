/**
 * 성과 보드의 안내 줄 (013 반복 2026-10-09b — spec FR-011b, research R13-19, `/speckit-analyze` I1).
 *
 * 메뉴 화면(예금·가상자산)과 비교 화면의 투자 시뮬레이션 모달이 **같은 함수**로 보드 안내 줄을 만든다. 글자를 두 곳에 두면 메뉴만 바뀐 날 모달이
 * 조용히 달라진다. 값은 서버 문자열에 형식만 입힌다(헌법 원칙 VI).
 */
import { formatAnnualRate, formatPercent, taxPercent } from "./format";
import type { CryptoCondition, CryptoSummary, DepositCondition, DepositSummary } from "./types";

/**
 * 정기예금 보드의 기준 줄 — 투자처·세율·지금 회차(008 FR-035). 결과가 어느 조건의 것인지 확인할 수 있어야 한다. `name`은 결과의 투자처 이름이다
 * (입력이 바뀌어도 결과의 것).
 */
export function depositBoardNotes(summary: DepositSummary, condition: DepositCondition | null, name: string): string[] {
  const notes = [name];
  if (condition !== null) notes.push(`세율 ${taxPercent(condition.interestTaxRate)}`);
  const term = summary.currentTerm;
  if (term !== null) {
    notes.push(`지금 회차 ${term.joinedOn} 가입 · ${formatAnnualRate(term.rate)} · 만기 ${term.maturesOn}`);
  }
  return notes;
}

/** 가상자산 일시금 보드의 기준 줄 — 매수일·수수료(007 ui-wireframes C3). 매수일이 시작 월 1일이 아니면(1일 결측) 그 날짜가 드러나야 한다. */
export function cryptoBoardNotes(summary: CryptoSummary, condition: CryptoCondition | null): string[] {
  const notes = [`매수일 ${summary.boughtOn}`];
  if (condition !== null) notes.push(`수수료 ${formatPercent(condition.tradeFeeRate, 2).replace("+", "")}`);
  return notes;
}
