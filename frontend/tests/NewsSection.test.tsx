/**
 * 대시보드 뉴스 칸 (014 T070) — FR-020~FR-022, FR-024, FR-025, SC-008, contracts D5.
 *
 * - 칸 머리: 나라·출처 이름(출처 화면 링크 — 새 탭)·목록 이름·받은 시각(한국 시간)·개수
 * - 줄: 차례·제목(새 탭 링크, opener 차단·리퍼러 없음)·언론사·시각·유료
 * - 시각: `publishedAt` → 한국 `HH:mm`(오늘이 아니면 `MM-DD HH:mm`), `publishedDate` → `MM-DD`, `publishedText`는 글자 그대로
 * - 실패: `parse_empty`는 "읽지 못함"(0건을 "뉴스 없음"으로 보이지 않는다), 그 밖은 까닭 + [다시 시도]
 */
import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NewsColumn } from "@/components/dashboard/NewsColumn";
import { NewsSection } from "@/components/dashboard/NewsSection";
import { apiClient } from "@/lib/apiClient";
import { initialColumns, useNewsStore } from "@/stores/newsStore";
import { failedOf, itemOf, newsOf } from "./support/newsFixtures";

/** 2026-10-09 22:40 한국 시간. */
const NOW = new Date("2026-10-09T13:40:00Z");

afterEach(() => {
  vi.restoreAllMocks();
  useNewsStore.setState({ columns: initialColumns() });
});

function column(props: Partial<Parameters<typeof NewsColumn>[0]> = {}) {
  const onRetry = vi.fn();
  render(
    <NewsColumn
      source="kr"
      state={{ status: "ready", list: newsOf("kr"), failure: null, seq: 1 }}
      onRetry={onRetry}
      now={NOW}
      {...props}
    />,
  );
  return onRetry;
}

describe("칸 머리", () => {
  it("나라·출처 이름(출처 화면 링크)·목록 이름·받은 시각·개수", () => {
    column();
    const head = screen.getByTestId("news-head");
    expect(head).toHaveTextContent("한국");
    const link = within(head).getByRole("link", { name: "네이버 증권" });
    expect(link).toHaveAttribute("href", "https://stock.naver.com/news");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(head).toHaveTextContent("주요뉴스");
    expect(head).toHaveTextContent("22:30 받음");
    expect(head).toHaveTextContent("10개");
  });

  it("미국·일본 칸의 이름", () => {
    render(
      <>
        <NewsColumn source="us" state={{ status: "ready", list: newsOf("us"), failure: null, seq: 1 }} onRetry={() => undefined} now={NOW} />
        <NewsColumn source="jp" state={{ status: "ready", list: newsOf("jp"), failure: null, seq: 1 }} onRetry={() => undefined} now={NOW} />
      </>,
    );
    const heads = screen.getAllByTestId("news-head");
    expect(heads[0]).toHaveTextContent("미국");
    expect(heads[0]).toHaveTextContent("Latest News");
    expect(heads[1]).toHaveTextContent("일본");
    expect(within(heads[1]).getByRole("link", { name: "Yahoo!ファイナンス" })).toHaveAttribute("href", "https://finance.yahoo.co.jp/news");
    expect(heads[1]).toHaveTextContent("ヘッドライン");
  });
});

describe("줄", () => {
  it("차례·제목 링크(새 탭, opener 차단)·언론사", () => {
    column();
    const rows = screen.getAllByTestId("news-row");
    expect(rows).toHaveLength(10);
    expect(rows[0]).toHaveTextContent("1");
    const link = within(rows[0]).getByRole("link", { name: "kr 기사 1" });
    expect(link).toHaveAttribute("href", "https://n.news.naver.com/article/015/0000000001");
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
    expect(rows[0]).toHaveTextContent("한국경제");
  });

  it("제목은 원문 그대로다", () => {
    const list = newsOf("jp", { items: [itemOf(1, { title: "〔NY外為〕円、158円台前半（9日朝）", url: "https://finance.yahoo.co.jp/news/detail/a" })] });
    column({ source: "jp", state: { status: "ready", list, failure: null, seq: 1 } });
    expect(screen.getByRole("link", { name: "〔NY外為〕円、158円台前半（9日朝）" })).toBeInTheDocument();
  });

  it("시각 — 오늘은 HH:mm, 지난 날은 MM-DD HH:mm, 날짜만은 MM-DD, 상대 표기는 그대로", () => {
    const list = newsOf("kr", {
      items: [
        itemOf(1, { publishedAt: "2026-10-09T13:12:14Z" }),
        itemOf(2, { publishedAt: "2026-10-08T07:41:10Z" }),
        itemOf(3, { publishedAt: null, publishedDate: "2026-10-08" }),
        itemOf(4, { publishedAt: null, publishedText: "4m ago" }),
        itemOf(5, { publishedAt: null }),
      ],
    });
    column({ state: { status: "ready", list, failure: null, seq: 1 } });
    const times = screen.getAllByTestId("news-row").map((r) => within(r).queryByTestId("news-time")?.textContent ?? null);
    expect(times).toEqual(["22:12", "10-08 16:41", "10-08", "4m ago", null]);
  });

  it("유료 기사에 유료를 단다", () => {
    const list = newsOf("jp", { items: [itemOf(1), itemOf(2, { paid: true })] });
    column({ source: "jp", state: { status: "ready", list, failure: null, seq: 1 } });
    const rows = screen.getAllByTestId("news-row");
    expect(within(rows[0]).queryByText("유료")).toBeNull();
    expect(within(rows[1]).getByText("유료")).toBeInTheDocument();
  });

  it("10개보다 적으면 있는 만큼과 그 개수", () => {
    const list = newsOf("kr", { items: [itemOf(1), itemOf(2), itemOf(3)] });
    column({ state: { status: "ready", list, failure: null, seq: 1 } });
    expect(screen.getAllByTestId("news-row")).toHaveLength(3);
    expect(screen.getByTestId("news-head")).toHaveTextContent("3개");
  });
});

describe("받는 중·실패", () => {
  it("받는 중", () => {
    column({ state: { status: "loading", list: null, failure: null, seq: 1 } });
    expect(screen.getByText("받는 중…")).toBeInTheDocument();
    expect(screen.getByTestId("news-head")).toHaveTextContent("한국");
  });

  it("parse_empty는 읽지 못함과 다시 시도", () => {
    const list = failedOf("jp", { reason: "parse_empty", message: "기사를 하나도 읽지 못했습니다.", retryAfterSeconds: 0 });
    const onRetry = column({ source: "jp", state: { status: "failed", list, failure: list.failure, seq: 1 } });
    expect(screen.getByText("읽지 못함 — 출처 화면이 바뀌었을 수 있음")).toBeInTheDocument();
    expect(screen.queryByText(/뉴스 없음/)).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("그 밖의 실패는 까닭과 남은 시간", () => {
    const list = failedOf("us", { reason: "rate_limited", message: "요청을 제한했습니다(429).", retryAfterSeconds: 42 });
    column({ source: "us", state: { status: "failed", list, failure: list.failure, seq: 1 } });
    expect(screen.getByText("받지 못했습니다 — 요청 제한")).toBeInTheDocument();
    expect(screen.getByText("42초 뒤 다시 시도할 수 있습니다")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument();
  });

  it.each([
    ["connection", "연결 실패"],
    ["blocked", "차단"],
    ["invalid_body", "읽을 수 없는 응답"],
  ] as const)("까닭 %s → %s", (reason, label) => {
    const list = failedOf("kr", { reason, message: "x", retryAfterSeconds: null });
    column({ state: { status: "failed", list, failure: list.failure, seq: 1 } });
    expect(screen.getByText(`받지 못했습니다 — ${label}`)).toBeInTheDocument();
    expect(screen.queryByText(/초 뒤 다시 시도할 수 있습니다/)).toBeNull();
  });

  it("서버 요청 실패", () => {
    const onRetry = column({ state: { status: "error", list: null, failure: null, seq: 1 } });
    expect(screen.getByText("뉴스를 불러오지 못했습니다.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});

describe("뉴스 칸 묶음", () => {
  it("세 칸이 한국·미국·일본 차례이고 출처를 밝힌다", async () => {
    vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => newsOf(path.split("/").pop() as "kr" | "us" | "jp"));
    render(<NewsSection />);
    expect(screen.getByRole("heading", { name: "오늘의 주요 경제 뉴스" })).toBeInTheDocument();
    await vi.waitFor(() => expect(screen.getAllByTestId("news-row")).toHaveLength(30));
    const heads = screen.getAllByTestId("news-head").map((h) => h.textContent ?? "");
    expect(heads[0]).toContain("한국");
    expect(heads[1]).toContain("미국");
    expect(heads[2]).toContain("일본");
    expect(screen.getByTestId("news-sources")).toHaveTextContent(
      "뉴스 출처: 네이버 증권 · Yahoo Finance · Yahoo!ファイナンス");
    expect(screen.getByTestId("news-sources")).toHaveTextContent("기사 본문은 가져오지 않습니다");
  });

  it("실패한 칸의 다시 시도는 그 칸만 부른다", async () => {
    const get = vi.spyOn(apiClient, "get").mockImplementation(async (path: string) => {
      if (path.endsWith("/us")) return failedOf("us", { reason: "connection", message: "x", retryAfterSeconds: null });
      return newsOf(path.endsWith("/kr") ? "kr" : "jp");
    });
    render(<NewsSection />);
    await vi.waitFor(() => expect(screen.getByRole("button", { name: "다시 시도" })).toBeInTheDocument());
    const before = get.mock.calls.length;
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await vi.waitFor(() => expect(get.mock.calls.length).toBe(before + 1));
    expect(get.mock.calls.at(-1)?.[0]).toBe("/api/dashboard/news/us");
  });
});
