"use client";

/**
 * 오늘의 주요 경제 뉴스 (014 T079) — FR-020, FR-024, FR-025, contracts D1·D5.
 *
 * 세 칸(한국·미국·일본)을 **따로** 받는다 — 화면이 셋을 동시에 부르고 온 것부터 그린다. 뉴스가 늦거나 실패해도 지표 카드는
 * 그대로다(FR-024). 출처를 밝히고, 목록(제목·언론사·시각·링크)만 보인다 — 기사 본문은 가져오지 않는다(FR-025).
 */
import { useEffect } from "react";
import { NewsColumn } from "@/components/dashboard/NewsColumn";
import { NEWS_SOURCES, useNewsStore } from "@/stores/newsStore";

export function NewsSection() {
  const columns = useNewsStore((s) => s.columns);
  const loadAll = useNewsStore((s) => s.loadAll);
  const retry = useNewsStore((s) => s.retry);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  return (
    <section aria-labelledby="news-heading" className="space-y-3">
      <h2 id="news-heading" className="text-base font-semibold text-gray-900">오늘의 주요 경제 뉴스</h2>
      <div className="grid gap-4 lg:grid-cols-3">
        {NEWS_SOURCES.map((source) => (
          <NewsColumn key={source} source={source} state={columns[source]} onRetry={() => void retry(source)} />
        ))}
      </div>
      <p data-testid="news-sources" className="text-xs text-gray-500">
        뉴스 출처: 네이버 증권 · Yahoo Finance · Yahoo!ファイナンス — 목록(제목·언론사·시각·링크)만 보이고 기사 본문은 가져오지 않습니다.
        저장하지 않고 서버가 잠시(기본 10분) 둡니다.
      </p>
    </section>
  );
}
