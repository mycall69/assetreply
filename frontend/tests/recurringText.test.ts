/**
 * 적립식 주기 안내 문장 (011 T017) — FR-003, ui-wireframes §1, research R11-11.
 *
 * - 날짜를 **계산하지 않는다** — 시작일 문자열의 요일·날짜 이름만 쓴다. 실제 납입일은 서버가 정한다(`noClientSideFinance`와 같은 선)
 * - 매주는 시작일의 요일, 매달은 시작일의 날짜(29~31일이면 "없는 달은 말일"), 매년은 시작일의 월·일(2월 29일이면 "평년은 2월 28일")
 * - 주식은 휴장이면 다음 거래일, 가상자산은 일봉이 없으면 다음 날
 * - 금액 칸의 이름은 투자 방식에 따라 "투자 원금" / "한 번 납입액"
 */
import { describe, expect, it } from "vitest";
import { amountLabel, frequencyNote } from "@/lib/recurringText";

describe("주기 안내", () => {
  it.each([
    ["daily", "2024-01-15", "거래일마다 넣습니다."],
    ["weekly", "2024-01-15", "매주 월요일(휴장이면 다음 거래일)에 넣습니다."],
    ["weekly", "2026-10-03", "매주 토요일(휴장이면 다음 거래일)에 넣습니다."],
    ["monthly", "2024-01-15", "매달 15일(휴장이면 다음 거래일)에 넣습니다."],
    ["monthly", "2024-01-31", "매달 31일(없는 달은 말일, 휴장이면 다음 거래일)에 넣습니다."],
    ["monthly", "2024-03-29", "매달 29일(없는 달은 말일, 휴장이면 다음 거래일)에 넣습니다."],
    ["yearly", "2024-01-15", "매년 1월 15일(휴장이면 다음 거래일)에 넣습니다."],
    ["yearly", "2024-02-29", "매년 2월 29일(평년은 2월 28일, 휴장이면 다음 거래일)에 넣습니다."],
  ] as const)("주식 %s %s", (frequency, start, text) => {
    expect(frequencyNote(frequency, start, "stock")).toBe(text);
  });

  it("가상자산은 날마다(UTC 하루)이고 일봉이 없으면 다음 날이다", () => {
    expect(frequencyNote("daily", "2024-01-15", "crypto")).toBe("날마다(UTC 하루) 넣습니다(일봉이 없으면 다음 날).");
    expect(frequencyNote("weekly", "2024-01-17", "crypto")).toBe("매주 수요일(일봉이 없으면 다음 날)에 넣습니다.");
  });

  it("시작일이 날짜가 아니면 문장이 없다", () => {
    expect(frequencyNote("monthly", "2024-13-01", "stock")).toBe("");
    expect(frequencyNote("weekly", "", "stock")).toBe("");
  });
});

describe("금액 칸 이름", () => {
  it("일시금은 투자 원금, 적립식은 한 번 납입액이다", () => {
    expect(amountLabel("lump_sum")).toBe("투자 원금");
    expect(amountLabel("recurring")).toBe("한 번 납입액");
  });
});
