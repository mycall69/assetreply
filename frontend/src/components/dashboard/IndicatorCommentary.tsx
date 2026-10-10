/**
 * 지표 모달의 변화 까닭 (014 반복 2026-10-10b T121) — FR-027, FR-022, SC-013, contracts D8.
 *
 * **문장을 만들지 않는다** — 출처의 시황 기사 제목·요약(원문 그대로)·언론사·시각을 보이고 제목을 기사로 건다(새 탭 — opener 차단·리퍼러
 * 없음). 까닭을 지어내면 틀려도 그럴듯해 보인다(FR-027 실패 양상).
 *
 * - 시각은 늘 날짜를 붙인다(한국 시간 `MM-DD HH:mm`) — 기사가 지난 세션부터 오늘까지 여러 날에 걸친다. 상대 표기("18h ago")는 글자 그대로다
 * - 없으면 "변화를 다룬 기사를 찾지 못했습니다", 실패면 까닭과 다시 시도(뉴스 칸과 같은 글자)
 */
import { NEWS_REASONS } from "@/components/dashboard/NewsColumn";
import { formatZonedDate, formatZonedTime, KST_ZONE } from "@/lib/kstClock";
import type { IndicatorCommentaryItem, NewsFailureReason } from "@/lib/types";
import type { CommentaryEntry } from "@/stores/indicatorCommentaryStore";

function itemTime(item: IndicatorCommentaryItem): string | null {
  if (item.publishedAt) {
    return `${formatZonedDate(item.publishedAt, KST_ZONE)} ${formatZonedTime(item.publishedAt, KST_ZONE)}`;
  }
  return item.publishedText;
}

function reasonText(reason: string | undefined): string {
  if (reason === "parse_empty") return "읽지 못함 — 출처 화면이 바뀌었을 수 있음";
  return (reason && NEWS_REASONS[reason as NewsFailureReason]) || "연결 실패";
}

function Retry({ onRetry }: { onRetry: () => void }) {
  return <button type="button" onClick={onRetry} className="text-sm text-gray-700 underline">다시 시도</button>;
}

export function IndicatorCommentary({ state, onRetry }: { state: CommentaryEntry; onRetry: () => void }) {
  const body = state.status === "ready" ? state.body : null;
  return (
    <section data-testid="indicator-commentary" aria-label="변화 까닭" className="space-y-2 rounded-lg border border-gray-200 p-3">
      <h3 className="text-sm font-semibold text-gray-900">변화 까닭</h3>
      {state.status === "loading" && <p className="text-sm text-gray-500">변화 까닭을 찾는 중…</p>}
      {state.status === "error" && (
        <div role="alert" className="space-y-1 text-sm text-amber-800">
          <p>까닭 기사를 받지 못했습니다 — 연결 실패</p>
          <Retry onRetry={onRetry} />
        </div>
      )}
      {body?.status === "failed" && (
        <div role="alert" className="space-y-1 text-sm text-amber-800">
          <p>까닭 기사를 받지 못했습니다 — {reasonText(body.failure?.reason)}</p>
          {body.failure?.retryAfterSeconds ? (
            <p className="text-xs">{body.failure.retryAfterSeconds}초 뒤 다시 시도할 수 있습니다</p>
          ) : null}
          <Retry onRetry={onRetry} />
        </div>
      )}
      {body?.status === "none" && <p className="text-sm text-gray-500">변화를 다룬 기사를 찾지 못했습니다</p>}
      {body?.status === "ok" && (
        <ul className="space-y-2">
          {body.items.map((item) => {
            const time = itemTime(item);
            return (
              <li key={item.url} data-testid="commentary-row" className="text-sm">
                <a href={item.url} target="_blank" rel="noopener noreferrer" className="break-words text-gray-900 hover:underline">
                  {item.title}
                </a>
                <p className="flex flex-wrap gap-x-2 text-xs text-gray-500">
                  {item.publisher && <span>{item.publisher}</span>}
                  {time && <span className="tabular-nums">{time}</span>}
                </p>
                {item.summary && <p className="mt-0.5 line-clamp-2 text-xs text-gray-600">{item.summary}</p>}
              </li>
            );
          })}
        </ul>
      )}
      {body && (
        <p className="text-xs text-gray-500">
          출처:{" "}
          <a href={body.sourceUrl} target="_blank" rel="noopener noreferrer" className="underline-offset-2 hover:underline">
            {body.source}
          </a>
        </p>
      )}
    </section>
  );
}
