/**
 * 지표 모달의 변화 까닭 (014 반복 2026-10-10b T109) — FR-027, FR-022, SC-013, contracts D8.
 *
 * - 줄: 제목(링크 — 새 탭, opener 차단·리퍼러 없음)·출처 이름·시각·요약(출처 원문). 시각은 늘 날짜를 붙인다(`MM-DD HH:mm` 한국 시간) —
 *   기사가 여러 날에 걸친다. 상대 표기는 글자 그대로다
 * - 없으면 "변화를 다룬 기사를 찾지 못했습니다" — 문장을 만들지 않는다
 * - 실패면 까닭과 다시 시도
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IndicatorCommentary } from "@/components/dashboard/IndicatorCommentary";
import { commentaryOf } from "./support/indicatorModalFixtures";

describe("성공", () => {
  it("줄의 칸과 새 탭 링크", () => {
    render(<IndicatorCommentary state={{ status: "ready", body: commentaryOf() }} onRetry={() => undefined} />);
    const region = screen.getByTestId("indicator-commentary");
    const link = within(region).getByRole("link", { name: "\"오픈AI 매출 기대 못 미친다\"…S&P500·나스닥 '하락' [뉴욕증시]" });
    expect(link).toHaveAttribute("href", "https://n.news.naver.com/mnews/article/015/0005340900");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(region).toHaveTextContent("한국경제");
    expect(region).toHaveTextContent("10-09 06:05");
    expect(region).toHaveTextContent("뉴욕증시가 하락 마감했다.");
    expect(region).toHaveTextContent("출처: 네이버 증권");
  });

  it("상대 표기는 글자 그대로다", () => {
    const body = commentaryOf({
      source: "Yahoo Finance", sourceUrl: "https://finance.yahoo.com/quote/%5EHSI/news/",
      items: [{ title: "Hong Kong Stocks End Higher", summary: null, publisher: "MT Newswires", publishedAt: null,
        publishedText: "18h ago", url: "https://finance.yahoo.com/news/hk-1.html" }],
    });
    render(<IndicatorCommentary state={{ status: "ready", body }} onRetry={() => undefined} />);
    expect(screen.getByTestId("indicator-commentary")).toHaveTextContent("18h ago");
  });

  it("상대 표기가 있으면 어림한 시각보다 먼저다", () => {
    // T123 실측(2026-10-10) — 서버는 Yahoo 상대 표기("19h ago")에서 어림한 `publishedAt`을 함께 싣는다(세션 이후 고르기용).
    // 어림한 값을 `MM-DD HH:mm`으로 보이면 출처에 없는 정확한 시각을 꾸며 낸다(뉴스 칸과 같은 규칙 — 상대 표기는 글자 그대로)
    const body = commentaryOf({
      source: "Yahoo Finance", sourceUrl: "https://finance.yahoo.com/quote/%5EHSI/news/",
      items: [{ title: "Xiaomi shares surge", summary: null, publisher: "Investing.com", publishedAt: "2026-10-09T06:43:37Z",
        publishedText: "19h ago", url: "https://finance.yahoo.com/news/x-1.html" }],
    });
    render(<IndicatorCommentary state={{ status: "ready", body }} onRetry={() => undefined} />);
    const region = screen.getByTestId("indicator-commentary");
    expect(region).toHaveTextContent("19h ago");
    expect(region).not.toHaveTextContent("10-09 15:43");
  });
});

describe("없음·실패·받는 중", () => {
  it("없으면 찾지 못함이다", () => {
    render(<IndicatorCommentary state={{ status: "ready", body: commentaryOf({ status: "none", items: [] }) }} onRetry={() => undefined} />);
    expect(screen.getByText("변화를 다룬 기사를 찾지 못했습니다")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /오픈AI/ })).toBeNull();
  });

  it("실패면 까닭과 다시 시도", () => {
    const onRetry = vi.fn();
    const body = commentaryOf({ status: "failed", items: [], failure: { reason: "rate_limited", message: "x", retryAfterSeconds: 42 } });
    render(<IndicatorCommentary state={{ status: "ready", body }} onRetry={onRetry} />);
    expect(screen.getByText("까닭 기사를 받지 못했습니다 — 요청 제한")).toBeInTheDocument();
    expect(screen.getByText("42초 뒤 다시 시도할 수 있습니다")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("받는 중", () => {
    render(<IndicatorCommentary state={{ status: "loading", body: null }} onRetry={() => undefined} />);
    expect(screen.getByText("변화 까닭을 찾는 중…")).toBeInTheDocument();
  });
});
