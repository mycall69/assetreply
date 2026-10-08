/**
 * 비교 표의 정렬 (013 T012) — FR-012, research R13-11.
 *
 * 값은 서버가 낸 소수 문자열이다. **글자 차례로 견주면 틀린다** — `"9.99"`가 `"10"`보다 뒤에 놓인다. `Number`로 바꾸면 큰 원화 금액·긴
 * 소수에서 정밀도를 잃는다(헌법 원칙 VI). 부호 → 정수부 길이 → 자릿수 차례로 견준다. 값이 없는 줄은 늘 끝이다.
 */
import { describe, expect, it } from "vitest";
import { compareDecimal, sortRows } from "@/lib/decimalOrder";

describe("compareDecimal", () => {
  it.each([
    ["9.99", "10", -1],
    ["10", "9.99", 1],
    ["-0.5", "0", -1],
    ["-10", "-0.5", -1],
    ["-0.5", "-10", 1],
    ["0.10", "0.1", 0],
    ["-0", "0", 0],
    ["123456789012345678.000001", "123456789012345678.000002", -1],
    ["1000000", "999999.999999", 1],
    ["0.000001", "0", 1],
    ["-2045.57", "-2045.570", 0],
  ])("%s 대 %s → %d", (a, b, expected) => {
    expect(compareDecimal(a, b)).toBe(expected);
  });
});

describe("sortRows", () => {
  const rows = [
    { name: "a", value: "10" },
    { name: "b", value: null },
    { name: "c", value: "9.99" },
    { name: "d", value: "-1" },
    { name: "e", value: "10" },
  ];

  it("오름차순은 수 차례이고 값이 없는 줄은 끝이다", () => {
    expect(sortRows(rows, (r) => r.value, "asc").map((r) => r.name)).toEqual(["d", "c", "a", "e", "b"]);
  });

  it("내림차순에서도 값이 없는 줄은 끝이다", () => {
    expect(sortRows(rows, (r) => r.value, "desc").map((r) => r.name)).toEqual(["a", "e", "c", "d", "b"]);
  });

  it("같은 값은 처음 차례를 지킨다(안정 정렬) — 받은 배열은 바꾸지 않는다", () => {
    const copy = [...rows];
    sortRows(rows, (r) => r.value, "desc");
    expect(rows).toEqual(copy);
  });
});
