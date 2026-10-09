/**
 * 대시보드 뉴스 칸 테스트의 응답 도우미 (014) — contracts/rest-api.md A5.
 *
 * 2026-10-09 22:30 한국 시간에 받은 모습을 기본으로 둔다.
 */
import type { NewsItem, NewsListResponse, NewsSourceKey } from "@/lib/types";

const HEADS: Record<NewsSourceKey, Pick<NewsListResponse, "sourceName" | "sourceUrl" | "list">> = {
  kr: { sourceName: "네이버 증권", sourceUrl: "https://stock.naver.com/news", list: "주요뉴스" },
  us: { sourceName: "Yahoo Finance", sourceUrl: "https://finance.yahoo.com/topic/latest-news/", list: "Latest News" },
  jp: { sourceName: "Yahoo!ファイナンス", sourceUrl: "https://finance.yahoo.co.jp/news", list: "ヘッドライン" },
};

export function itemOf(rank: number, over: Partial<NewsItem> = {}): NewsItem {
  return {
    rank,
    title: `기사 제목 ${rank}`,
    url: `https://n.news.naver.com/article/015/${String(rank).padStart(10, "0")}`,
    publisher: "한국경제",
    publishedAt: "2026-10-09T13:12:14Z",
    publishedDate: null,
    publishedText: null,
    paid: false,
    ...over,
  };
}

export function newsOf(source: NewsSourceKey, over: Partial<NewsListResponse> = {}): NewsListResponse {
  return {
    source,
    ...HEADS[source],
    status: "ok",
    fetchedAt: "2026-10-09T13:30:00Z",
    items: Array.from({ length: 10 }, (_, i) => itemOf(i + 1, { title: `${source} 기사 ${i + 1}` })),
    failure: null,
    ...over,
  };
}

export function failedOf(source: NewsSourceKey, failure: NewsListResponse["failure"]): NewsListResponse {
  return newsOf(source, { status: "failed", fetchedAt: null, items: [], failure });
}
