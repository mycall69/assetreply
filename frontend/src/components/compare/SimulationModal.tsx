"use client";

/**
 * 투자 시뮬레이션 모달 (013 반복 2026-10-09b T102) — spec FR-011b, ui-wireframes F10, research R13-19.
 *
 * 비교 표의 줄에서 연다. 그 줄을 낸 실행의 조건으로 그 자산군 메뉴의 결과(투자 결과 패널·성과 추이·일자별 투자 성과)를 메뉴와 같은 부품으로 그린다
 * (`detail/*`). 응답은 모달 스토어가 메뉴 경로에서 받는다 — 이 부품은 계산하지 않는다(헌법 원칙 VI).
 *
 * - `role="dialog"`·`aria-modal`. ×·Esc·바깥(배경) 누름으로 닫는다
 * - 열면 포커스가 닫기 단추로, 닫으면 연 단추로 돌아간다 — 연 단추가 포커스를 받지 못했으면(단추를 눌러도 포커스를 주지 않는 브라우저) 그 줄의
 *   단추(`data-simulate-key`)를 찾아 돌아간다. **Tab·Shift+Tab은 모달 안에서 돈다** — `aria-modal`만으로는 브라우저가 가두지 않는다
 *   (뒤의 비교 화면 단추에 닿으면 보이지 않는 곳에서 비교를 다시 실행한다 — FR-011b 실패 양상)
 * - 열린 동안 배경(`body`) 스크롤을 잠그고 닫으면 되돌린다
 * - 수집 중(202)은 진행을 구독하지 않고 까닭과 다시 시도만이다(R13-19)
 */
import { useEffect, useRef } from "react";
import { ExternalLink } from "@/components/ExternalLink";
import { FREQUENCY_TEXT } from "@/components/recurring/InvestmentModeFields";
import { ASSET_LABEL, METHOD_LABEL, type CompareCondition } from "@/lib/compareCondition";
import { formatMoneyWithSymbol } from "@/lib/format";
import type {
  CryptoSimulationResponse,
  DepositSimulationResponse,
  InstallmentResponse,
  RealEstateSimulationResponse,
  RecurringCryptoResponse,
  RecurringStockResponse,
  SimulationResponse,
} from "@/lib/types";
import { useCompareDetailStore, type DetailState } from "@/stores/compareDetailStore";
import { CryptoDetail } from "./detail/CryptoDetail";
import { DepositDetail } from "./detail/DepositDetail";
import { RealEstateDetail } from "./detail/RealEstateDetail";
import { StockDetail } from "./detail/StockDetail";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea, [tabindex]:not([tabindex='-1'])";

/** 머리의 조건 — 자산군·방식(주기)·시작일(매입일)·금액·통화·재투자. 그 줄을 낸 실행의 조건이다(흐린 동안에도). */
function conditionText(c: CompareCondition): string {
  const parts: string[] = [`${c.asset === "realestate" ? "매입일" : "시작일"} ${c.start}`];
  if (c.amount !== null) {
    const amount = formatMoneyWithSymbol(c.amount, c.principalCurrency);
    parts.push(c.method === "recurring" ? `${FREQUENCY_TEXT[c.frequency ?? "monthly"]} ${amount}`
      : c.method === "installment" ? `월 ${amount}` : amount);
  }
  if (c.reinvest !== null) parts.push(c.reinvest ? "배당 재투자" : "배당 재투자 안 함");
  return parts.join(" · ");
}

function Body({ state }: { state: DetailState }) {
  const { open, status, menu } = state;
  if (open === null) return null;
  if (status === "loading" || status === "idle") return <p className="py-8 text-center text-sm text-gray-500">계산하는 중…</p>;
  if (status !== "ok" || menu === null) {
    return (
      <div role="alert" className="flex flex-wrap items-center gap-2 rounded border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
        <span>{state.reason}</span>
        <button type="button" onClick={() => void state.retry()}
          className="rounded border border-amber-300 bg-white px-2 py-0.5 text-amber-800 hover:bg-amber-100">
          다시 시도
        </button>
      </div>
    );
  }
  const c = open.condition;
  switch (c.asset) {
    case "stock":
      return <StockDetail menu={menu as SimulationResponse | RecurringStockResponse} recurring={c.method === "recurring"}
        principalCurrency={c.principalCurrency} state={state} />;
    case "crypto":
      return <CryptoDetail menu={menu as CryptoSimulationResponse | RecurringCryptoResponse} recurring={c.method === "recurring"}
        principalCurrency={c.principalCurrency} state={state} />;
    case "deposit":
      return <DepositDetail menu={menu as DepositSimulationResponse | InstallmentResponse} installment={c.method === "installment"}
        state={state} />;
    case "realestate":
      return <RealEstateDetail menu={menu as RealEstateSimulationResponse} state={state} />;
  }
}

export function SimulationModal() {
  const state = useCompareDetailStore();
  const { open, menu, close } = state;
  const panel = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const returnTo = useRef<HTMLElement | null>(null);
  const key = open?.key ?? null;

  // 열 때 연 단추를 기억하고 닫기 단추로 포커스, 배경 스크롤을 잠근다. 닫으면 되돌린다.
  useEffect(() => {
    if (key === null) return;
    const active = document.activeElement;
    returnTo.current = active instanceof HTMLElement && active !== document.body ? active : null;
    closeButton.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      const back = returnTo.current !== null && document.contains(returnTo.current) ? returnTo.current
        : document.querySelector<HTMLElement>(`[data-simulate-key="${key.replace(/["\\]/g, "\\$&")}"]`);
      back?.focus();
    };
  }, [key]);

  useEffect(() => {
    if (key === null) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== "Tab" || panel.current === null) return;
      const items = [...panel.current.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !panel.current.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !panel.current.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [key, close]);

  if (open === null) return null;
  const c = open.condition;
  const asOf = menu !== null ? (menu.summary as { asOf?: string }).asOf ?? null : null;
  const method = c.method === "recurring" && c.frequency !== null ? `${METHOD_LABEL[c.method]} ${FREQUENCY_TEXT[c.frequency]}` : METHOD_LABEL[c.method];
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 sm:p-8"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby="simulation-modal-title" data-testid="simulation-modal"
        className="max-h-[90vh] w-full max-w-[1200px] overflow-y-auto rounded-lg bg-white shadow-xl">
        <header className="sticky top-0 z-10 flex items-start justify-between gap-4 border-b border-gray-200 bg-white px-5 py-4">
          <div className="min-w-0 space-y-1">
            <h2 id="simulation-modal-title" className="text-lg font-semibold">
              <ExternalLink href={open.href} label={`${open.name} 새 탭에서 보기`}>{open.name}</ExternalLink>
              <span className="ml-2 text-sm font-normal text-gray-500">투자 시뮬레이션 · {ASSET_LABEL[c.asset]} · {method}</span>
            </h2>
            <p data-testid="simulation-modal-condition" className="text-xs text-gray-500">
              {conditionText(c)}{asOf !== null ? ` · 기준일 ${asOf}` : ""}
            </p>
          </div>
          <button ref={closeButton} type="button" aria-label="투자 시뮬레이션 닫기" onClick={close}
            className="rounded px-2 text-xl leading-none text-gray-500 hover:text-gray-900">
            ×
          </button>
        </header>
        <div className="space-y-5 px-5 py-4">
          <Body state={state} />
        </div>
      </div>
    </div>
  );
}
