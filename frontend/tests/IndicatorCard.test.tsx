/**
 * 지표 카드 (014 T026) — FR-004~FR-007, FR-009, FR-015, FR-018, SC-009, contracts D2.
 *
 * 카드는 서버 문자열에 형식만 입힌다(원칙 VI). 다섯 상태와 잠정·확정 전·지연, 전일의 출처, 주석, 실패·새로 받지 못함을 보인다.
 * 오르면 ▲ 빨강, 내리면 ▼ 파랑, 변화 없음은 회색 — 색만으로 구별하지 않는다(▲·▼·부호).
 */
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IndicatorCard } from "@/components/dashboard/IndicatorCard";
import type { DashboardIndicator } from "@/lib/types";
import { indicatorOf, quoteOf } from "./support/dashboardFixtures";

function card(indicator: DashboardIndicator, onRetry = vi.fn()) {
  render(<ul><IndicatorCard indicator={indicator} onRetry={onRetry} /></ul>);
  return onRetry;
}

describe("값과 오르내림", () => {
  it("휴장 KOSPI — ▼ 파랑, 등락률 쉼표 형식, 마지막 거래일과 전일", () => {
    card(indicatorOf("kospi"));
    expect(screen.getByTestId("card-value")).toHaveTextContent("6,625.93");
    const change = screen.getByTestId("card-change");
    expect(change).toHaveTextContent("▼ 177.97");
    expect(change).toHaveTextContent("-2.61%");
    expect(change.className).toContain("text-blue-700");
    expect(screen.getByTestId("card-state")).toHaveTextContent("휴장 · 10-08 종가");
    expect(screen.getByTestId("card-previous")).toHaveTextContent("전일 10-07");
  });

  it("오르면 ▲ 빨강과 +", () => {
    card(indicatorOf("sp500", { quote: quoteOf({ change: "28.060000", changeRate: "0.003613", direction: "up" }) }));
    const change = screen.getByTestId("card-change");
    expect(change).toHaveTextContent("▲ 28.06");
    expect(change).toHaveTextContent("+0.36%");
    expect(change.className).toContain("text-red-700");
  });

  it("변화가 없으면 화살표 없이 회색", () => {
    card(indicatorOf("kospi", { quote: quoteOf({ change: "0.000000", changeRate: "0.000000", direction: "flat" }) }));
    const change = screen.getByTestId("card-change");
    expect(change.textContent).not.toMatch(/[▲▼]/);
    expect(change.className).toContain("text-gray-500");
  });

  it("단위를 보인다", () => {
    card(indicatorOf("gold"));
    expect(screen.getByText("USD/트로이온스")).toBeInTheDocument();
  });
});

describe("장 상태", () => {
  it("장중 — ⏳ 잠정, 현지·한국 시각, 지연", () => {
    card(indicatorOf("sp500", {
      quote: quoteOf({ state: "open", provisional: true, valueTime: "2026-10-09T14:30:00Z", sessionDate: "2026-10-09", delayMinutes: 10 }),
    }));
    const state = screen.getByTestId("card-state");
    expect(state).toHaveTextContent("장중 ⏳ 잠정");
    expect(state).toHaveTextContent("10:30 (한국 23:30)");
    expect(state).toHaveTextContent("약 10분 지연");
  });

  it("점심 휴장 — ⏳ 잠정", () => {
    card(indicatorOf("nikkei225", {
      quote: quoteOf({ state: "break", provisional: true, valueTime: "2026-10-09T02:30:00Z", sessionDate: "2026-10-09" }),
    }));
    expect(screen.getByTestId("card-state")).toHaveTextContent("점심 휴장 ⏳ 잠정 · 11:30");
  });

  it("개장 전 — 지난 거래일 종가", () => {
    card(indicatorOf("kospi", { quote: quoteOf({ state: "pre_open", sessionDate: "2026-10-08" }) }));
    expect(screen.getByTestId("card-state")).toHaveTextContent("개장 전 · 10-08 종가");
  });

  it("오늘 마감은 ⏳ 확정 전, 지난 거래일 마감은 ⏳ 없음", () => {
    const { unmount } = render(<ul><IndicatorCard onRetry={vi.fn()} indicator={indicatorOf("sp500", {
      quote: quoteOf({ state: "closed", provisional: true, valueTime: "2026-10-08T20:00:00Z", sessionDate: "2026-10-08" }),
    })} /></ul>);
    expect(screen.getByTestId("card-state")).toHaveTextContent("마감 ⏳ 확정 전 · 16:00 (한국 05:00)");
    unmount();
    card(indicatorOf("sp500", { quote: quoteOf({ state: "closed", provisional: false, sessionDate: "2026-10-08" }) }));
    expect(screen.getByTestId("card-state")).toHaveTextContent("마감 · 10-08 종가");
    expect(screen.getByTestId("card-state").textContent).not.toContain("⏳");
  });

  it("한국 시장은 시각을 한 번만 보인다", () => {
    card(indicatorOf("kospi", { quote: quoteOf({ state: "open", provisional: true, valueTime: "2026-10-08T01:00:00Z" }) }));
    expect(screen.getByTestId("card-state")).toHaveTextContent("장중 ⏳ 잠정 · 10:00");
    expect(screen.getByTestId("card-state").textContent).not.toContain("한국");
  });
});

describe("전일과 주석", () => {
  it("이력이 닿지 않으면 출처 전일을 밝힌다", () => {
    card(indicatorOf("kospi", { quote: quoteOf({ previous: { close: "6803.900000", date: null, from: "source" } }) }));
    expect(screen.getByTestId("card-previous")).toHaveTextContent("전일 값: 출처(이력에 아직 없음)");
  });

  it("시장 환율 — 런던 0시 기준과 주석", () => {
    card(indicatorOf("usd", { quote: quoteOf({ previous: { close: "1342.560000", date: null, from: "source_fx" } }) }));
    expect(screen.getByTestId("card-previous")).toHaveTextContent("전일: 런던 0시 기준(출처)");
    expect(screen.getByText("시장 환율 — 매매기준율과 다를 수 있음")).toBeInTheDocument();
  });

  it("선물 근월물 주석", () => {
    card(indicatorOf("wti"));
    expect(screen.getByText("선물 근월물 연속")).toBeInTheDocument();
  });

  it("등락률을 낼 수 없으면 —와 설명", () => {
    card(indicatorOf("wti", { quote: quoteOf({ changeRate: null, changeRateBlank: "non_positive_base", change: "47.640000", direction: "up" }) }));
    const rate = screen.getByTestId("card-rate");
    expect(rate).toHaveTextContent("—");
    expect(rate.getAttribute("title")).toBe("직전 값이 0 이하라 등락률을 낼 수 없습니다");
  });
});

describe("실패", () => {
  it("새로 받지 못함 — 마지막 값과 기준 시각, 다시 시도", () => {
    const onRetry = card(indicatorOf("kospi", { stale: true, failure: { kind: "rate_limited", message: "한도" } }));
    expect(screen.getByTestId("card-value")).toHaveTextContent("6,625.93");
    expect(screen.getByTestId("card-stale")).toHaveTextContent("새로 받지 못함 · 10-08 20:05");
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("값이 한 번도 없으면 —와 까닭", () => {
    card(indicatorOf("shanghai", { status: "failed", quote: null, failure: { kind: "connection", message: "시세 출처에 연결하지 못했습니다." } }));
    expect(screen.getByTestId("card-value")).toHaveTextContent("—");
    expect(screen.getByText("시세 출처에 연결하지 못했습니다.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });
});

describe("링크", () => {
  it("카드는 지표 화면 링크이고 접근 이름은 추이 보기", () => {
    card(indicatorOf("sp500"));
    const link = screen.getByRole("link", { name: "S&P 500 추이 보기" });
    expect(link).toHaveAttribute("href", "/dashboard/sp500");
  });
});
