"use client";

/**
 * 종목 검색 (T040) — 005 FR-002a, FR-002b, contracts/ui-wireframes.md W1.
 *
 * **코드를 직접 입력하는 칸을 두지 않는다.** 입력 칸은 검색어를 받는 자리이고, 확정은
 * 목록에서 고르는 것으로만 이루어진다. 직접 입력하게 하면 시장별 코드 체계를 사용자가
 * 알아야 하고, **오타와 "없는 종목"을 구별할 수 없다** — 둘 다 "시세를 얻을 수 없음"으로
 * 보이는데 사용자가 할 일은 정반대다.
 *
 * **검색 실패와 "결과 없음"을 다르게 말한다.** 출처가 죽었는데 "없습니다"라고 하면
 * 사용자는 그 종목이 존재하지 않는다고 읽는다.
 */

import { useEffect, useRef, useState } from "react";
import { ApiError, apiClient } from "@/lib/apiClient";
import type { StockSearchResult } from "@/lib/types";

/** 입력이 멎은 뒤 검색한다. 글자마다 부르면 출처 호출을 낭비한다. */
const DEBOUNCE_MS = 300;

interface SearchResponse {
  query: string;
  results: StockSearchResult[];
}

export function StockSearch({
  value,
  onSelect,
}: {
  value: StockSearchResult | null;
  onSelect: (stock: StockSearchResult) => void;
}) {
  const [term, setTerm] = useState("");
  const [results, setResults] = useState<StockSearchResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [active, setActive] = useState(-1);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 검색어가 비는 것은 **사용자의 조작**이라 이벤트 핸들러에서 치운다. 효과 안에서
  // 동기적으로 상태를 비우면 연쇄 렌더가 생긴다.
  const changeTerm = (next: string) => {
    setTerm(next);
    if (next.trim() === "") {
      setResults([]);
      setSearched(false);
      setError(null);
    }
  };

  useEffect(() => {
    const query = term.trim();
    if (query === "") return;

    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = setTimeout(() => {
      void (async () => {
        try {
          const body = await apiClient.get<SearchResponse>(
            `/api/stocks/search?q=${encodeURIComponent(query)}`,
          );
          setResults(body.results);
          setError(null);
          setSearched(true);
          setActive(-1);
        } catch (err) {
          // 결과 없음과 **다르게** 말한다.
          setError(
            err instanceof ApiError ? err.message : "검색하지 못했습니다.",
          );
          setResults([]);
          setSearched(false);
        }
      })();
    }, DEBOUNCE_MS);
    return () => {
      if (timer.current !== null) clearTimeout(timer.current);
    };
  }, [term]);

  const choose = (stock: StockSearchResult) => {
    onSelect(stock);
    changeTerm("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (results.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, results.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && active >= 0) {
      e.preventDefault();
      choose(results[active]);
    }
  };

  return (
    <div className="relative">
      <label className="flex items-center gap-2 text-sm">
        <span className="w-12 text-gray-500">종목</span>
        <input
          type="search"
          role="searchbox"
          aria-label="종목 검색"
          aria-autocomplete="list"
          value={term}
          placeholder="이름이나 코드로 검색"
          onChange={(e) => changeTerm(e.target.value)}
          onKeyDown={onKeyDown}
          className="flex-1 rounded border border-gray-300 px-3 py-1.5"
        />
      </label>

      {value !== null && term === "" && (
        <p className="mt-1 pl-14 text-sm">
          <span className="font-semibold">{value.name}</span>{" "}
          <span className="text-xs text-gray-500">
            {value.market} · {value.currency}
          </span>
        </p>
      )}

      {error !== null && (
        <p role="alert" className="mt-1 pl-14 text-xs text-red-700">
          {error}
        </p>
      )}

      {searched && results.length === 0 && (
        <p className="mt-1 pl-14 text-xs text-gray-500">
          해당하는 종목을 찾지 못했습니다.
        </p>
      )}

      {results.length > 0 && (
        <ul
          role="listbox"
          aria-label="검색 결과"
          className="absolute left-14 right-0 z-10 mt-1 max-h-60 overflow-auto rounded border border-gray-300 bg-white shadow"
        >
          {results.map((r, i) => (
            <li key={`${r.market}:${r.symbol}`}>
              <button
                type="button"
                role="option"
                aria-selected={i === active}
                onClick={() => choose(r)}
                className={`flex w-full items-baseline justify-between px-3 py-2 text-left text-sm ${
                  i === active ? "bg-gray-100" : "hover:bg-gray-50"
                }`}
              >
                <span>{r.name}</span>
                {/* FR-002b — 시장과 통화를 함께 보인다. */}
                <span className="ml-3 text-xs text-gray-500">
                  {r.market} · {r.currency}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
