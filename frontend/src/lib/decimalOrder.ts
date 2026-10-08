/**
 * 소수 문자열의 차례 (013 T029) — FR-012, research R13-11.
 *
 * 비교 표의 값은 서버가 낸 소수 문자열이다. **글자 차례로 견주면 틀린다**(`"9.99"`가 `"10"`보다 뒤). 수로 바꾸면 큰 원화 금액·긴 소수에서
 * 정밀도를 잃는다(헌법 원칙 VI). 부호 → 정수부 길이 → 자릿수 차례로 견준다. 정렬은 계산이 아니라 견주기다 — 값을 만들지 않는다.
 */

interface Parsed {
  negative: boolean;
  whole: string;
  fraction: string;
}

function parse(value: string): Parsed {
  const text = value.trim();
  const negative = text.startsWith("-");
  const digits = text.replace(/^[-+]/, "");
  const [rawWhole = "", rawFraction = ""] = digits.split(".");
  const whole = rawWhole.replace(/^0+/, "");
  const fraction = rawFraction.replace(/0+$/, "");
  // `-0`·`-0.000`은 0이다 — 부호를 떼어 0과 같게 둔다.
  const zero = whole === "" && fraction === "";
  return { negative: negative && !zero, whole, fraction };
}

/** 크기만 견준다(부호 무시). */
function compareMagnitude(a: Parsed, b: Parsed): number {
  if (a.whole.length !== b.whole.length) return a.whole.length < b.whole.length ? -1 : 1;
  if (a.whole !== b.whole) return a.whole < b.whole ? -1 : 1;
  const width = Math.max(a.fraction.length, b.fraction.length);
  const fa = a.fraction.padEnd(width, "0");
  const fb = b.fraction.padEnd(width, "0");
  if (fa === fb) return 0;
  return fa < fb ? -1 : 1;
}

/** 두 소수 문자열을 수 차례로 견준다 — 작으면 -1, 같으면 0, 크면 1. */
export function compareDecimal(a: string, b: string): number {
  const pa = parse(a);
  const pb = parse(b);
  if (pa.negative !== pb.negative) return pa.negative ? -1 : 1;
  const magnitude = compareMagnitude(pa, pb);
  // 같으면 0 — 음수끼리 `-0`을 내지 않는다.
  if (magnitude === 0) return 0;
  return pa.negative ? -magnitude : magnitude;
}

/**
 * 값으로 정렬한 새 배열. 값이 없는(`null`) 줄은 오름·내림 모두 끝이다. 같은 값은 처음 차례를 지킨다(안정 정렬). 받은 배열은 바꾸지 않는다.
 */
export function sortRows<T>(rows: readonly T[], value: (row: T) => string | null, direction: "asc" | "desc"): T[] {
  const sign = direction === "asc" ? 1 : -1;
  return rows
    .map((row, index) => ({ row, index, key: value(row) }))
    .sort((a, b) => {
      if (a.key === null || b.key === null) {
        if (a.key === b.key) return a.index - b.index;
        return a.key === null ? 1 : -1;
      }
      return sign * compareDecimal(a.key, b.key) || a.index - b.index;
    })
    .map((item) => item.row);
}
