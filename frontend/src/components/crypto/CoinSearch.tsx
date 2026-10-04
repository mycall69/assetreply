"use client";

/**
 * 코인 검색 (T020) — 007 FR-003~FR-006, FR-005b, ui-wireframes C2, analyze C2.
 *
 * **로컬 코인 목록에서 찾는다.** 서버가 출처를 부르지 않고 갱신도 기다리지 않는다 — 그래서 응답의 `list`가 "결과 없음"과
 * "목록 없음"을 가른다. 같은 빈 화면이 둘을 함께 뜻하면 할 일이 정반대인데 구별할 수 없다.
 *
 * **같은 심볼은 이름과 순위로 구별한다**(FR-004). 고른 것은 `coinId`로 넘긴다 — 심볼은 유일하지 않다.
 *
 * 목록을 처음 받거나 새로 받는 중이면 **진행 스트림을 구독해** 받은 쪽 수를 실시간으로 보이고, 끝나면 검색을 다시 보낸다
 * (FR-005b). 처음 받는 목록은 약 2분 걸린다 — 진행이 보이지 않으면 사용자는 멈춘 것으로 읽는다.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiClient } from "@/lib/apiClient";
import { subscribeCoinListProgress } from "@/lib/cryptoListProgressStream";
import { formatKst } from "@/lib/format";
import { createSequence } from "@/lib/searchSequence";
import type {
  CoinListProgress,
  CoinListReason,
  CoinListStatus,
  CoinRef,
  CoinSearchResponse,
  CoinSearchResult,
} from "@/lib/types";

/** 입력 대기. 주식 로컬 검색과 같다(006 research R6-5). */
export const COIN_DEBOUNCE_MS = 150;

const REASON_TEXT: Record<CoinListReason, string> = {
  blocked: "시세 출처가 접근을 막았습니다.",
  format: "출처의 응답 형식이 예상과 다릅니다.",
  network: "출처에 연결하지 못했습니다.",
  shrunk: "받은 목록이 이전보다 크게 줄어 교체하지 않았습니다.",
};

const EDITION_LABEL = { en: "영문", ko: "한국어" } as const;

function progressText(progress: CoinListProgress | null): string {
  if (progress === null || progress.edition === null) return "";
  const label = EDITION_LABEL[progress.edition];
  return progress.pagesExpected === null
    ? ` · ${label} ${progress.pagesDone}쪽 받음`
    : ` · ${label} ${progress.pagesDone}/${progress.pagesExpected}쪽`;
}

interface StreamFailure {
  reason: CoinListReason;
}

/** 목록 상태 줄 (ui-wireframes C2). */
function statusLines(
  list: CoinListStatus,
  progress: CoinListProgress | null,
  failure: StreamFailure | null,
): string[] {
  const at = list.asOf === null ? null : formatKst(list.asOf);
  const reason = failure?.reason ?? (list.state === "failed" ? list.reason : undefined);
  const lines: string[] = [];
  if (reason !== undefined) {
    lines.push(at === null
      ? `코인 목록을 받지 못했습니다 — ${REASON_TEXT[reason]} 다음 날 첫 검색 때 다시 받습니다.`
      : `목록을 새로 받지 못했습니다 — ${REASON_TEXT[reason]} 이전 목록 기준 ${at}`);
  } else if (list.state === "never") {
    lines.push(`코인 목록을 처음 받는 중입니다${progressText(progress)}`);
  } else if (list.state === "refreshing") {
    lines.push(`목록을 새로 받는 중${progressText(progress)} — 이전 목록으로 찾습니다 (목록 기준 ${at})`);
  } else {
    lines.push(`목록 기준 ${at}`);
  }
  if (list.koreanNames.state === "failed" && list.state !== "never") {
    lines.push("한글 이름을 새로 받지 못했습니다 — 저장된 한글 이름과 영문 이름·심볼로 찾습니다.");
  }
  return lines;
}

/** 목록이 있어 "결과 없음"이라 말할 수 있는가. */
const hasList = (list: CoinListStatus) => list.asOf !== null;

const rankText = (rank: number | null | undefined) =>
  (rank === null || rank === undefined ? "" : `#${rank.toLocaleString("en-US")}`);

const message = (err: unknown) =>
  err instanceof ApiError ? err.message : "코인을 검색하지 못했습니다.";

export function CoinSearch({
  value,
  onSelect,
}: {
  /** 고른 코인 — 검색 결과 또는 이력에서 다시 실행한 코인(순위가 없을 수 있다). */
  value: CoinRef | null;
  onSelect: (coin: CoinSearchResult) => void;
}) {
  const [term, setTerm] = useState("");
  const [found, setFound] = useState<CoinSearchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [active, setActive] = useState(-1);
  const [progress, setProgress] = useState<CoinListProgress | null>(null);
  const [failure, setFailure] = useState<StreamFailure | null>(null);
  // 진행 스트림이 끝나면 올려 같은 검색어로 다시 묻는다.
  const [reload, setReload] = useState(0);
  const seq = useRef(createSequence());

  // 검색어가 비는 것은 사용자의 조작이라 이벤트 처리기에서 치운다(006 StockSearch와 같다).
  const changeTerm = (next: string) => {
    setTerm(next);
    setActive(-1);
    if (next.trim() === "") {
      seq.current.invalidate();
      setFound(null);
      setError(null);
    }
  };

  useEffect(() => {
    const query = term.trim();
    if (query === "") return;
    const timer = setTimeout(() => {
      const id = seq.current.next();
      void (async () => {
        try {
          const body = await apiClient.get<CoinSearchResponse>(
            `/api/crypto/search?q=${encodeURIComponent(query)}`);
          if (!seq.current.isLatest(id)) return;
          setFound(body);
          setError(null);
        } catch (err) {
          if (!seq.current.isLatest(id)) return;
          setFound(null);
          setError(message(err));
        }
      })();
    }, COIN_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [term, reload]);

  const listState = found?.list.state;
  const watching = listState === "never" || listState === "refreshing";

  useEffect(() => {
    if (!watching) return;
    const unsubscribe = subscribeCoinListProgress({
      onSnapshot: (next) => {
        setProgress(next);
        setFailure(null);
      },
      onCompleted: () => {
        setProgress(null);
        setReload((n) => n + 1);
      },
      onFailed: (reason) => {
        setProgress(null);
        setFailure({ reason });
      },
    });
    return () => {
      unsubscribe();
      setProgress(null);
    };
  }, [watching]);

  const options = useMemo(() => found?.results ?? [], [found]);

  const choose = (coin: CoinSearchResult) => {
    onSelect(coin);
    changeTerm("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    // 한글 조합 중의 키 입력은 입력기의 것이다(006 버그 search-enter-ime). 조합 중 엔터에서 고르고 칸을 비우면 입력기가
    // 조합 중이던 글자를 빈 칸에 확정해 넣는다. keyCode 229도 본다 — Safari는 확정을 keydown보다 먼저 보낸다.
    if (e.nativeEvent.isComposing || e.keyCode === 229) return;
    if (options.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      // 고른 항목이 없으면 맨 위 결과다(FR-003).
      e.preventDefault();
      choose(options[active >= 0 && active < options.length ? active : 0]);
    }
  };

  const open = term.trim() !== "";
  const lines = found === null ? [] : statusLines(found.list, progress, failure);

  return (
    <div className="relative">
      <label className="flex items-center gap-2 text-sm">
        <span className="w-12 text-gray-500">코인</span>
        <input
          type="search"
          role="searchbox"
          aria-label="코인 검색"
          aria-autocomplete="list"
          value={term}
          placeholder="이름·심볼·초성으로 검색 (예: btc, 비트코인, ㅂㅌㅋㅇ)"
          onChange={(e) => changeTerm(e.target.value)}
          onKeyDown={onKeyDown}
          className="flex-1 rounded border border-gray-300 px-3 py-1.5"
        />
      </label>

      {value !== null && term === "" && (
        <p data-testid="coin-selected" className="mt-1 pl-14 text-sm">
          {value.nameKo !== null && <span className="font-semibold">{value.nameKo} </span>}
          <span className={value.nameKo === null ? "font-semibold" : "text-gray-700"}>
            {value.name}
          </span>{" "}
          <span className="text-xs text-gray-500">
            {value.symbol} · {value.currency} {rankText(value.rank)}
          </span>
        </p>
      )}

      {open && (
        <div className="absolute left-14 right-0 z-10 mt-1 max-h-96 overflow-auto rounded border border-gray-300 bg-white shadow">
          {lines.length > 0 && (
            <div role="status" data-testid="coin-list-status"
              className="border-b border-gray-100 px-3 py-1 text-xs text-gray-500">
              {lines.map((line) => <p key={line}>{line}</p>)}
            </div>
          )}
          {error !== null && (
            <p role="alert" className="px-3 py-1 text-xs text-red-700">{error}</p>
          )}
          {options.length > 0 && (
            <ul role="listbox" aria-label="코인 검색 결과" className="py-1">
              {options.map((coin, index) => (
                <li key={coin.coinId}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={index === active}
                    onClick={() => choose(coin)}
                    className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm ${
                      index === active ? "bg-gray-100" : "hover:bg-gray-50"
                    }`}
                  >
                    <span>
                      {coin.nameKo !== null && <span className="font-medium">{coin.nameKo} </span>}
                      <span className={coin.nameKo === null ? "font-medium" : "text-gray-600"}>
                        {coin.name}
                      </span>
                      {coin.listStatus === "missing" && (
                        // 색만으로 전달하지 않는다 — 글자로 쓴다(ui-wireframes 접근성).
                        <span className="ml-2 text-xs text-amber-700">목록에서 빠짐</span>
                      )}
                    </span>
                    <span className="shrink-0 text-xs tabular-nums text-gray-500">
                      {coin.symbol} · {coin.currency}{coin.rank !== null && <> {rankText(coin.rank)}</>}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          {found !== null && options.length === 0 && hasList(found.list) && (
            <p className="px-3 py-2 text-xs text-gray-500">해당하는 코인을 찾지 못했습니다.</p>
          )}
          {found?.truncated === true && (
            <p className="px-3 py-1 text-xs text-gray-500">결과가 더 있습니다. 검색어를 더 입력하세요.</p>
          )}
        </div>
      )}
    </div>
  );
}
