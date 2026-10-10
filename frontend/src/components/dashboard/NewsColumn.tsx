/**
 * 뉴스 칸 하나 (014 T079) — FR-020~FR-022, FR-024, FR-025, contracts D5.
 *
 * - 머리: 나라·출처 이름(출처 화면 링크 — 새 탭)·목록 이름·받은 시각(한국 시간)·개수
 * - 줄: 차례·**원문 그대로의 제목**(새 탭 — opener 차단·리퍼러 없음)·언론사·시각·`유료`
 * - 시각: 정확한 시각은 한국 `HH:mm`(받은 날과 다른 날이면 `MM-DD HH:mm`), 날짜만이면 `MM-DD`, 상대 표기는 글자 그대로 —
 *   시각을 꾸며 내지 않는다(FR-021). "오늘"의 기준은 칸의 받은 시각이다(화면이 지금 시각을 읽지 않는다 — 같은 응답이면 같은 글자)
 * - 실패: 0건 읽기는 "읽지 못함"이다 — "뉴스 없음"으로 보이지 않는다(FR-024)
 */
import { formatZonedDate, formatZonedDay, formatZonedTime, KST_ZONE, shortDate } from "@/lib/kstClock";
import type { NewsFailureReason, NewsItem, NewsSourceKey } from "@/lib/types";
import type { NewsColumnState } from "@/stores/newsStore";

const COUNTRY: Record<NewsSourceKey, string> = { kr: "한국", us: "미국", jp: "일본" };

/** 응답이 오기 전의 머리 — 받은 뒤에는 서버의 이름을 쓴다. */
const HEADS: Record<NewsSourceKey, { name: string; url: string; list: string }> = {
  kr: { name: "네이버 증권", url: "https://stock.naver.com/news", list: "주요뉴스" },
  us: { name: "Yahoo Finance", url: "https://finance.yahoo.com/topic/latest-news/", list: "Latest News" },
  jp: { name: "Yahoo!ファイナンス", url: "https://finance.yahoo.co.jp/news", list: "ヘッドライン" },
};

/** 출처 실패의 까닭 글자 — 변화 까닭 칸(반복 2026-10-10b)도 같은 글자다. */
export const NEWS_REASONS: Record<NewsFailureReason, string> = {
  connection: "연결 실패",
  blocked: "차단",
  rate_limited: "요청 제한",
  parse_empty: "읽지 못함",
  invalid_body: "읽을 수 없는 응답",
};

/** 줄의 시각 글자. 없으면 `null`. `reference`는 "오늘"을 정하는 시각(ISO)이다. */
export function newsTime(item: NewsItem, reference: string | null): string | null {
  if (item.publishedAt) {
    const time = formatZonedTime(item.publishedAt, KST_ZONE);
    const sameDay = reference !== null
      && formatZonedDay(item.publishedAt, KST_ZONE) === formatZonedDay(reference, KST_ZONE);
    return sameDay ? time : `${formatZonedDate(item.publishedAt, KST_ZONE)} ${time}`;
  }
  if (item.publishedDate) return shortDate(item.publishedDate);
  return item.publishedText;
}

function RetryButton({ onRetry }: { onRetry: () => void }) {
  return <button type="button" onClick={onRetry} className="text-sm text-gray-700 underline">다시 시도</button>;
}

export function NewsColumn({ source, state, onRetry, now }: {
  source: NewsSourceKey;
  state: NewsColumnState;
  onRetry: () => void;
  /** "오늘"의 기준. 없으면 칸의 받은 시각이다. */
  now?: Date;
}) {
  const list = state.list;
  const head = list ? { name: list.sourceName, url: list.sourceUrl, list: list.list } : HEADS[source];
  const reference = now ? now.toISOString() : list?.fetchedAt ?? null;
  const ready = state.status === "ready" && list !== null;
  return (
    <section data-testid="news-column" data-source={source}
      className="min-w-0 flex-1 basis-80 rounded-lg border border-gray-200 p-4">
      <header data-testid="news-head" className="mb-2 space-y-0.5">
        <h3 className="text-sm font-semibold text-gray-900">
          {COUNTRY[source]} ·{" "}
          <a href={head.url} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
            {head.name}
          </a>
        </h3>
        <p className="text-xs text-gray-500">
          {head.list}
          {ready && list.fetchedAt && <> · {formatZonedTime(list.fetchedAt, KST_ZONE)} 받음</>}
          {ready && <> · {list.items.length}개</>}
        </p>
      </header>
      {(state.status === "idle" || state.status === "loading") && <p className="text-sm text-gray-500">받는 중…</p>}
      {ready && (
        <ol className="divide-y divide-gray-100">
          {list.items.map((item) => {
            const time = newsTime(item, reference);
            return (
              <li key={`${item.rank}-${item.url}`} data-testid="news-row" className="flex gap-2 py-1.5 text-sm">
                <span className="w-5 shrink-0 text-right tabular-nums text-gray-400">{item.rank}</span>
                <div className="min-w-0 flex-1">
                  <a href={item.url} target="_blank" rel="noopener noreferrer"
                    className="break-words text-gray-900 hover:underline">{item.title}</a>
                  <p className="flex flex-wrap gap-x-2 text-xs text-gray-500">
                    {item.publisher && <span>{item.publisher}</span>}
                    {time && <span data-testid="news-time" className="tabular-nums">{time}</span>}
                    {item.paid && <span className="rounded bg-amber-50 px-1 text-amber-800">유료</span>}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
      {state.status === "failed" && (
        <div role="alert" className="space-y-1 text-sm text-amber-800">
          {state.failure?.reason === "parse_empty"
            ? <p>읽지 못함 — 출처 화면이 바뀌었을 수 있음</p>
            : <p>받지 못했습니다 — {state.failure ? NEWS_REASONS[state.failure.reason] : "연결 실패"}</p>}
          {state.failure?.retryAfterSeconds ? (
            <p className="text-xs">{state.failure.retryAfterSeconds}초 뒤 다시 시도할 수 있습니다</p>
          ) : null}
          <RetryButton onRetry={onRetry} />
        </div>
      )}
      {state.status === "error" && (
        <div role="alert" className="space-y-1 text-sm text-amber-800">
          <p>뉴스를 불러오지 못했습니다.</p>
          <RetryButton onRetry={onRetry} />
        </div>
      )}
    </section>
  );
}
