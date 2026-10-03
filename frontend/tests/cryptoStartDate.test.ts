/**
 * 가상자산 시작일 상한 (T028) — 007 FR-009, FR-022, ui-wireframes C1.
 *
 * 계산 끝은 **UTC 어제**(마지막으로 마감된 UTC 하루)다. 주식의 `localYesterday`(한국 시간)를 쓰면 한국 오전 9시 전에는 아직
 * 마감되지 않은 UTC 하루를 고를 수 있다 — 서버는 그 일봉을 저장하지 않으므로 시작일이 계산 끝보다 늦어 거절된다.
 */
import { describe, expect, it } from "vitest";
import { localYesterday, utcYesterday } from "@/lib/startDate";

describe("utcYesterday", () => {
  it("한국 오전 9시 전에는 한국 어제보다 하루 이르다", () => {
    // 2026-10-03 00:30 KST = 2026-10-02 15:30 UTC
    const now = new Date("2026-10-02T15:30:00Z");
    expect(utcYesterday(now)).toBe("2026-10-01");
  });

  it("한국 오전 9시 뒤에는 한국 어제와 같다", () => {
    const now = new Date("2026-10-03T01:00:00Z");
    expect(utcYesterday(now)).toBe("2026-10-02");
  });

  it("월초에는 지난달 마지막 날이다", () => {
    expect(utcYesterday(new Date("2026-03-01T12:00:00Z"))).toBe("2026-02-28");
  });

  it("주식의 지역 어제는 그대로다", () => {
    expect(typeof localYesterday()).toBe("string");
  });
});
