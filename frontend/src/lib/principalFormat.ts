/**
 * 원금 칸의 쉼표 (006 FR-053, research R6-20) — 반복 2026-10-03.
 *
 * **쉼표는 표시에만 있다.** 화면 상태·요청·이력에는 쉼표 없는 문자열이 간다 — 서버는 원금을
 * `Decimal`로 읽어 쉼표가 섞이면 400을 낸다(헌법 원칙 VI, 원금은 문자열 그대로). 서버가 쉼표를
 * 받게 하지 않는다: 거절 규칙을 느슨하게 하면 다른 경로의 틀린 입력도 통과한다.
 */

/** 친 글자에서 숫자와 **첫 소수점**만 남긴다. 쉼표·공백·단위는 버린다. */
export function normalizePrincipal(typed: string): string {
  let out = "";
  let seenDot = false;
  for (const ch of typed) {
    if (ch >= "0" && ch <= "9") {
      out += ch;
    } else if (ch === "." && !seenDot) {
      seenDot = true;
      out += ch;
    }
  }
  return out;
}

/** 정수부만 3자리마다 쉼표로 묶는다. 소수부는 친 그대로 둔다 — 반올림하지 않는다. */
export function formatPrincipal(raw: string): string {
  const dot = raw.indexOf(".");
  const whole = dot === -1 ? raw : raw.slice(0, dot);
  const fraction = dot === -1 ? "" : raw.slice(dot);
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",") + fraction;
}

/**
 * 표시 문자열에서 숫자(·소수점) `count`개 뒤의 위치.
 *
 * 쉼표가 끼어들면 글자 수가 바뀌어 커서가 끝으로 튄다. 고치기 전 커서 앞의 숫자 개수를 세어 두었다가
 * 다시 그린 뒤 같은 개수의 숫자 뒤로 커서를 옮긴다.
 */
export function caretAfter(shown: string, count: number): number {
  if (count <= 0) return 0;
  let seen = 0;
  for (let i = 0; i < shown.length; i += 1) {
    if (shown[i] !== ",") {
      seen += 1;
      if (seen === count) return i + 1;
    }
  }
  return shown.length;
}
