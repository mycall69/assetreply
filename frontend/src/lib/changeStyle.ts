/**
 * 등락 칸의 기호·색 (014 반복 2026-10-10d·2026-10-13b) — 외환 일자별 표(FR-031)와 주식·가상자산 투자 성과표(FR-047)가 같은 값을 쓴다.
 *
 * 요약 칸(`RateSummary`)과 같은 색 — 오름 빨강·내림 파랑·같음 회색. 색만으로 전하지 않는다(▲·▼). 블랙 배경의 값은 `globals.css`의 `.dark` 재정의다.
 */

export type ChangeDirection = "up" | "down" | "flat";

export const TONE: Record<ChangeDirection, string> = { up: "text-red-600", down: "text-blue-600", flat: "text-gray-500" };
export const ARROW: Record<ChangeDirection, string> = { up: "▲ ", down: "▼ ", flat: "" };
