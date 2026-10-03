"use client";

/**
 * 종목 검색 (T043) — 006 FR-024~029a, contracts/ui-wireframes W2·W2a. 005 T040을 잇는다.
 *
 * **두 영역을 따로 채운다.** 국내·미국은 로컬 목록 검색으로 곧바로, 일본은 외부
 * 검색이 오는 대로(FR-027). 한꺼번에 내려고 외부 응답을 기다리면 로컬 목록을 둔
 * 이유(속도)가 사라지고, 외부 출처가 막히면 국내·미국 종목까지 찾을 수 없게 된다.
 * 외부 검색의 실패는 일본 영역에만 표시한다(SC-015).
 *
 * **코드를 직접 입력하는 칸을 두지 않는다**(005 SC-031). 확정은 목록에서 고르는
 * 것으로만 이루어진다. 고른 것은 **선택**으로 알린다 — 종목 식별은 등록 응답이
 * 정한다(FR-030b).
 *
 * **"결과 없음"과 "목록 없음"을 가른다**(FR-028, SC-006). 같은 빈 화면이 둘을 함께
 * 뜻하면 사용자는 할 일이 정반대인데 구별할 수 없다.
 *
 * **늦게 온 이전 결과는 그리지 않는다**(FR-029a). 로컬·외부가 번호를 따로 가진다.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError, apiClient } from "@/lib/apiClient";
import { nameWithCode } from "@/lib/displayCode";
import { formatKst } from "@/lib/format";
import { createSequence } from "@/lib/searchSequence";
import type {
  ExternalSearchResponse,
  ExternalStockResult,
  ListingUnitStatus,
  LocalSearchResponse,
  LocalStockResult,
  StockChoice,
  StockKind,
  StockSearchResult,
} from "@/lib/types";

/**
 * 로컬 검색의 입력 대기. SC-001의 0.5초는 입력 대기를 포함한다 — 005의 300ms는
 * 예산의 60%를 쓴다(research R6-5).
 */
export const LOCAL_DEBOUNCE_MS = 150;
/** 외부 검색은 005 그대로. 글자마다 부르면 출처 호출을 낭비한다. */
export const EXTERNAL_DEBOUNCE_MS = 300;

const KIND_LABEL: Partial<Record<StockKind, string>> = { etf: "ETF", reit: "리츠" };

const REASON_TEXT: Record<string, string> = {
  auth_missing: "키움증권 인증 정보가 설정되지 않았습니다.",
  auth_failed: "키움증권 인증에 실패했습니다.",
  rate_limit: "목록 출처의 호출 한도에 걸렸습니다.",
  network: "목록 출처에 연결하지 못했습니다.",
  invalid: "목록 출처의 응답이 올바르지 않습니다.",
};

function actionText(status: ListingUnitStatus): string {
  if (status.action === "set_credentials") {
    return status.reason === "auth_failed"
      ? "인증 정보를 확인하고 백엔드를 다시 시작하세요."
      : ".env에 KIWOOM_APP_KEY·KIWOOM_APP_SECRET을 넣고 백엔드를 다시 시작하세요.";
  }
  if (status.action === "retry_later") return "잠시 뒤 다시 검색하세요.";
  return "잠시 기다리면 목록을 받습니다.";
}

/**
 * 목록이 없어 "결과 없음"이라 말할 수 없는 단위 (W2a). 받는 중이라도 이전 목록이
 * 있으면 그것으로 답하므로 여기 들지 않는다(FR-017).
 */
function isProblem(status: ListingUnitStatus): boolean {
  return status.state === "never"
    || status.state === "auth_blocked"
    || (status.state === "refreshing" && status.asOf === null);
}

function unitLine(status: ListingUnitStatus): string {
  const at = status.asOf === null ? null : formatKst(status.asOf);
  switch (status.state) {
    case "refreshing":
      return at === null ? `${status.unit} 받는 중` : `${status.unit} 갱신 중(${at} 목록)`;
    case "failed":
      return `${status.unit} ${at} (갱신 실패)`;
    case "auth_blocked":
      return at === null ? `${status.unit} 없음` : `${status.unit} ${at} (인증 실패)`;
    case "never":
      return `${status.unit} 없음`;
    default:
      return `${status.unit} ${at}`;
  }
}

interface NoticeGroup {
  key: string;
  units: string[];
  title: string;
  reason: string | null;
  action: string;
}

function noticeGroups(lists: ListingUnitStatus[]): NoticeGroup[] {
  const groups = new Map<string, NoticeGroup>();
  for (const status of lists.filter(isProblem)) {
    const key = `${status.state}|${status.reason ?? ""}|${status.action ?? ""}`;
    const found = groups.get(key);
    if (found !== undefined) {
      found.units.push(status.unit);
      continue;
    }
    groups.set(key, {
      key,
      units: [status.unit],
      title: status.state === "refreshing" ? "종목 목록을 받는 중입니다." : "종목 목록을 받지 못했습니다.",
      reason: status.reason === undefined ? null : (REASON_TEXT[status.reason] ?? null),
      action: actionText(status),
    });
  }
  return [...groups.values()];
}

type Option =
  | { source: "listing"; item: LocalStockResult }
  | { source: "external"; item: ExternalStockResult };

const optionKey = (o: Option) =>
  o.source === "listing" ? `l:${o.item.listingId}` : `e:${o.item.market}:${o.item.symbol}`;

function toChoice(o: Option): StockChoice {
  return o.source === "listing"
    ? { source: "listing", listingId: o.item.listingId, preview: o.item }
    : { source: "external", result: o.item };
}

const message = (err: unknown, fallback: string) =>
  err instanceof ApiError ? err.message : fallback;

export function StockSearch({
  value,
  onSelect,
}: {
  value: StockSearchResult | null;
  onSelect: (choice: StockChoice) => void;
}) {
  const [term, setTerm] = useState("");
  const [local, setLocal] = useState<LocalSearchResponse | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [external, setExternal] = useState<ExternalSearchResponse | null>(null);
  const [externalError, setExternalError] = useState<string | null>(null);
  const [externalLoading, setExternalLoading] = useState(false);
  const [active, setActive] = useState(-1);

  const localSeq = useRef(createSequence());
  const externalSeq = useRef(createSequence());

  // 검색어가 비는 것은 **사용자의 조작**이라 이벤트 핸들러에서 치운다. 효과 안에서
  // 동기적으로 상태를 비우면 연쇄 렌더가 생긴다. 나가 있던 요청의 응답도 버린다.
  const changeTerm = (next: string) => {
    setTerm(next);
    setActive(-1);
    if (next.trim() === "") {
      localSeq.current.invalidate();
      externalSeq.current.invalidate();
      setLocal(null);
      setLocalError(null);
      setExternal(null);
      setExternalError(null);
      setExternalLoading(false);
    }
  };

  useEffect(() => {
    const query = term.trim();
    if (query === "") return;
    const path = `?q=${encodeURIComponent(query)}`;

    const localTimer = setTimeout(() => {
      const id = localSeq.current.next();
      void (async () => {
        try {
          const body = await apiClient.get<LocalSearchResponse>(`/api/stocks/search${path}`);
          if (!localSeq.current.isLatest(id)) return;
          setLocal(body);
          setLocalError(null);
        } catch (err) {
          if (!localSeq.current.isLatest(id)) return;
          // 결과 없음과 **다르게** 말한다.
          setLocal(null);
          setLocalError(message(err, "국내·미국 종목을 검색하지 못했습니다."));
        }
      })();
    }, LOCAL_DEBOUNCE_MS);

    const externalTimer = setTimeout(() => {
      const id = externalSeq.current.next();
      setExternalLoading(true);
      void (async () => {
        try {
          const body = await apiClient.get<ExternalSearchResponse>(
            `/api/stocks/search/external${path}`);
          if (!externalSeq.current.isLatest(id)) return;
          setExternal(body);
          setExternalError(null);
        } catch (err) {
          if (!externalSeq.current.isLatest(id)) return;
          setExternal(null);
          setExternalError(message(err, "일본 종목을 검색하지 못했습니다."));
        } finally {
          if (externalSeq.current.isLatest(id)) setExternalLoading(false);
        }
      })();
    }, EXTERNAL_DEBOUNCE_MS);

    return () => {
      clearTimeout(localTimer);
      clearTimeout(externalTimer);
    };
  }, [term]);

  const localOptions = useMemo<Option[]>(
    () => (local?.results ?? []).map((item) => ({ source: "listing", item })), [local]);
  const externalOptions = useMemo<Option[]>(
    () => (external?.results ?? []).map((item) => ({ source: "external", item })), [external]);
  const options = useMemo(() => [...localOptions, ...externalOptions],
    [localOptions, externalOptions]);

  const choose = (option: Option) => {
    onSelect(toChoice(option));
    changeTerm("");
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (options.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((i) => Math.min(i + 1, options.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter") {
      // 006 FR-056 — 고른 항목이 없으면 **맨 위 결과**(국내·미국 첫 줄, 없으면 일본 첫 줄)다. 아무 반응이
      // 없으면 사용자는 검색이 멈춘 것으로 읽는다.
      e.preventDefault();
      choose(options[active >= 0 && active < options.length ? active : 0]);
    }
  };

  const open = term.trim() !== "";
  const lists = local?.lists ?? [];
  const groups = noticeGroups(lists);

  const renderOption = (option: Option, index: number) => {
    const item = option.item;
    const kind = KIND_LABEL[item.kind];
    return (
      <li key={optionKey(option)}>
        <button
          type="button"
          role="option"
          aria-selected={index === active}
          onClick={() => choose(option)}
          className={`flex w-full items-baseline justify-between gap-3 px-3 py-2 text-left text-sm ${
            index === active ? "bg-gray-100" : "hover:bg-gray-50"
          }`}
        >
          <span>
            {/* 006 FR-025 — 종목명(코드). 이름이 비슷한 종목을 코드로 구별한다. */}
            {nameWithCode(item)}
            {kind !== undefined && (
              <span className="ml-2 rounded border border-gray-300 px-1 text-xs text-gray-600">
                {kind}
              </span>
            )}
            {option.source === "listing" && option.item.country === "US"
              && option.item.nameEn !== null && (
              // FR-025 — 미국 종목은 영문명을 함께 보인다. 한글명이 비슷한 종목이 여럿이면
              // 영문명이 구별의 근거다.
              <span data-name-en className="ml-2 text-xs text-gray-500">
                {option.item.nameEn}
              </span>
            )}
            {option.source === "listing" && option.item.listingStatus === "missing" && (
              // 색만으로 전달하지 않는다 — 글자로 쓴다 (ui-wireframes 접근성).
              <span className="ml-2 text-xs text-amber-700">목록에서 빠짐</span>
            )}
          </span>
          {/* 005 FR-002b — 시장과 통화를 함께 보인다. */}
          <span className="shrink-0 text-xs text-gray-500">
            {item.market} · {item.currency}
          </span>
        </button>
      </li>
    );
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
          placeholder="이름·초성·코드로 검색 (예: ㅅㅅㅈㅈ)"
          onChange={(e) => changeTerm(e.target.value)}
          onKeyDown={onKeyDown}
          className="flex-1 rounded border border-gray-300 px-3 py-1.5"
        />
      </label>

      {value !== null && term === "" && (
        <p className="mt-1 pl-14 text-sm">
          <span className="font-semibold">{nameWithCode(value)}</span>{" "}
          <span className="text-xs text-gray-500">
            {value.market} · {value.currency}
          </span>
        </p>
      )}

      {open && (
        <div className="absolute left-14 right-0 z-10 mt-1 max-h-96 overflow-auto rounded border border-gray-300 bg-white shadow">
          <section aria-label="국내·미국" className="py-1">
            <h4 className="px-3 pt-1 text-xs font-semibold text-gray-500">국내·미국</h4>
            {localError !== null && (
              <p role="alert" className="px-3 py-1 text-xs text-red-700">{localError}</p>
            )}
            {localOptions.length > 0 && (
              <ul role="listbox" aria-label="국내·미국 검색 결과">
                {localOptions.map((o, i) => renderOption(o, i))}
              </ul>
            )}
            {local?.truncated === true && (
              <p className="px-3 py-1 text-xs text-gray-500">
                결과가 더 있습니다. 검색어를 더 입력하세요.
              </p>
            )}
            {local !== null && localOptions.length === 0 && groups.length === 0 && (
              <p className="px-3 py-1 text-xs text-gray-500">해당하는 종목을 찾지 못했습니다.</p>
            )}
            {groups.length > 0 && (
              <div role="status" data-testid="listing-notice" className="space-y-1 px-3 py-2 text-xs text-gray-700">
                {groups.map((g) => (
                  <p key={g.key}>
                    ⓘ {g.units.join("·")} {g.title}
                    {g.reason !== null && <> {g.reason}</>} {g.action}
                  </p>
                ))}
              </div>
            )}
            {lists.length > 0 && (
              <p data-testid="listing-asof" className="border-t border-gray-100 px-3 py-1 text-xs text-gray-400">
                목록 기준 {lists.map(unitLine).join(" · ")}
              </p>
            )}
          </section>

          <section aria-label="일본" className="border-t-2 border-gray-200 py-1">
            <h4 className="px-3 pt-1 text-xs font-semibold text-gray-500">일본</h4>
            {externalLoading && external === null && externalError === null && (
              <p className="px-3 py-1 text-xs text-gray-400">검색 중…</p>
            )}
            {externalError !== null && (
              <p role="alert" className="px-3 py-1 text-xs text-red-700">{externalError}</p>
            )}
            {externalOptions.length > 0 && (
              <ul role="listbox" aria-label="일본 검색 결과">
                {externalOptions.map((o, i) => renderOption(o, localOptions.length + i))}
              </ul>
            )}
            {external !== null && externalOptions.length === 0 && (
              <p className="px-3 py-1 text-xs text-gray-500">일본 종목을 찾지 못했습니다.</p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
