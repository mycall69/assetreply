/**
 * 한도 소진 배너 검증 (T066) — FR-026, SC-012, ui-wireframes W4.
 *
 * **"지금까지 받은 데이터는 그대로 유효합니다"가 FR-026의 요구다.** 이 문장이 없으면
 * 사용자는 한도 소진을 데이터 손실로 오해한다.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RateLimitBanner } from "@/components/collection/RateLimitBanner";

describe("배너", () => {
  it("한도 소진임을 알린다", () => {
    render(<RateLimitBanner currency="USD" coveredThrough="2024-03-16" />);
    expect(screen.getByText(/호출 한도를 모두 썼습니다/)).toBeTruthy();
  });

  it("도달 지점을 보여준다", () => {
    render(<RateLimitBanner currency="USD" coveredThrough="2024-03-16" />);
    expect(screen.getByText(/2024-03-16까지 받고 멈췄습니다/)).toBeTruthy();
  });

  it("데이터가 유효함을 알린다 (FR-026)", () => {
    render(<RateLimitBanner currency="USD" coveredThrough="2024-03-16" />);
    expect(screen.getByText(/그대로 유효합니다/)).toBeTruthy();
  });

  it("통화를 바꿔도 풀리지 않음을 알린다", () => {
    // 전환하면 풀린다고 오해하면 헛수고한다.
    render(<RateLimitBanner currency="USD" coveredThrough="2024-03-16" />);
    expect(screen.getByText(/다른 통화로 바꿔도 오늘은 시작할 수 없습니다/)).toBeTruthy();
  });

  it("일반 실패와 구별되는 알림 역할이다 (SC-012)", () => {
    render(<RateLimitBanner currency="USD" coveredThrough={null} />);
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
