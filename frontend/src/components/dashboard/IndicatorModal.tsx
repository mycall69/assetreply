"use client";

/**
 * 지표 모달 (014 반복 2026-10-10b T121) — FR-010, FR-016, contracts D3·D4, research R14-20.
 *
 * 대시보드 위에 뜬다 — 카드를 누르면(대시보드 안 이동) 모달 경로가 가로채고(`mode="intercepted"`), 새로고침·주소 직접 입력은 대시보드와
 * 같은 모달이다(`mode="direct"`). 내용은 `IndicatorView`다.
 *
 * - `role="dialog"`·`aria-modal`. ✕·Esc·바깥(배경) 누름으로 닫는다 — 가로챈 모달은 `router.back()`(브라우저 뒤로와 같다), 직접 연 모달은
 *   `router.replace("/dashboard")`(뒤로 가면 사이트 밖으로 나갈 수 있다)
 * - 열면 포커스가 닫기 단추로, 사라지면(뒤로 가기로 사라져도) **그 카드의 링크**(`data-indicator`)로 돌아간다 — 돌려주지 않으면 키보드
 *   사용자가 자리를 잃는다. Tab·Shift+Tab은 모달 안에서 돈다(`aria-modal`만으로는 브라우저가 가두지 않는다 — 013 `SimulationModal`과 같다)
 * - 열린 동안 배경(`body`) 스크롤을 잠근다
 * - 머리 값은 대시보드와 같은 스토어다. 갱신 주기는 뒤의 대시보드가 진다 — 모달이 닫힐 때 멈추면 대시보드 카드의 갱신까지 멈춘다
 */
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef } from "react";
import { IndicatorView } from "@/components/dashboard/IndicatorView";
import type { IndicatorRange } from "@/lib/types";
import { useMarketQuotesStore } from "@/stores/marketQuotesStore";

const FOCUSABLE = "a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea, [tabindex]:not([tabindex='-1'])";
const TITLE_ID = "indicator-modal-title";

function focusCard(id: string): boolean {
  const link = document.querySelector<HTMLElement>(`[data-indicator="${id.replace(/["\\]/g, "\\$&")}"] a`);
  link?.focus();
  return link !== null;
}

export function IndicatorModal({ id, range, mode }: { id: string; range: IndicatorRange; mode: "intercepted" | "direct" }) {
  const router = useRouter();
  const panel = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const load = useMarketQuotesStore((s) => s.load);
  const startPolling = useMarketQuotesStore((s) => s.startPolling);

  const close = useCallback(() => {
    if (mode === "intercepted") router.back();
    else router.replace("/dashboard", { scroll: false });
  }, [mode, router]);

  useEffect(() => {
    if (useMarketQuotesStore.getState().data === null) void load();
    startPolling();
  }, [load, startPolling]);

  // 열면 닫기 단추로 포커스, 배경 스크롤을 잠근다. 사라지면 되돌리고 그 카드로 포커스를 돌린다.
  useEffect(() => {
    closeButton.current?.focus();
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = overflow;
      // 직접 연 모달을 닫으면 대시보드가 새로 그려진다 — 그 카드가 아직 없으면 다음 그리기에서 한 번 더 찾는다
      if (!focusCard(id)) requestAnimationFrame(() => focusCard(id));
    };
  }, [id]);

  useEffect(() => {
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
  }, [close]);

  return (
    <div data-testid="indicator-modal-backdrop"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 p-4 sm:p-8"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) close();
      }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={TITLE_ID} data-testid="indicator-modal"
        className="relative max-h-[90vh] w-full max-w-[1100px] overflow-y-auto rounded-lg bg-white px-5 pb-5 pt-4 shadow-xl">
        <button ref={closeButton} type="button" aria-label="지표 닫기" onClick={close}
          className="absolute right-3 top-3 rounded px-2 text-xl leading-none text-gray-500 hover:text-gray-900">
          ×
        </button>
        <IndicatorView id={id} range={range} titleId={TITLE_ID} onClose={close} />
      </div>
    </div>
  );
}
