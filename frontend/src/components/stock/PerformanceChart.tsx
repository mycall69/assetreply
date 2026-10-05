"use client";

/**
 * 성과 차트 (T082) — 005 FR-033, FR-034, FR-041, ui-wireframes W3. 006 FR-068 — 기준은 응답의
 * `basisCurrency`(KRW)다. 원금 통화로 쓰면 달러 원금 실행의 KRW 값을 달러로 읽는다.
 *
 * **잔고와 수익률을 다른 축에 둔다.** 8만과 0.2를 한 축에 놓으면 수익률 선이 바닥에
 * 붙어 평평해 보이고, 사용자는 그 종목이 움직이지 않았다고 읽는다. 오류는 나지 않는다.
 *
 * **결측 렌더링은 001의 규칙을 그대로 쓴다** (FR-034, 001 FR-032). 휴장일은 잇고
 * 미수집은 끊는다 — 미수집을 이으면 구멍 위에 온전한 선이 그려져 사용자가 데이터를
 * 다 가졌다고 믿는다. 같은 `splitSeriesAtGaps`를 부르므로 자산군마다 규칙이 갈릴
 * 수 없다.
 *
 * **축 눈금에 천 단위 쉼표를 넣는다**(007 FR-043a, 반복 2026-10-04) — 잔고는 기준 통화 자릿수(KRW 소수점 없음), 수익률은
 * 소수 2자리. 축 형식은 시리즈 옵션이라 **구간마다** 준다 — 첫 구간에만 주면 축이 다른 시리즈를 따를 때 쉼표가 빠진다.
 *
 * **잠정 구간은 연한 색이다**(008 FR-036, research R8-10). 응답의 `provisionalFrom`부터 같은 두 선을 같은 축·같은 축 형식에
 * 연한 색으로 이어 그리고 범례가 "잠정(날짜부터)"을 말한다 — 같은 색이면 잠정 값을 확정 값으로 읽는다(헌법 원칙 V). 경계
 * 점은 양쪽에 넣는다 — 빼면 선이 끊겨 결측처럼 보인다. 주식·가상자산은 이 키가 없어 지금과 같다.
 *
 * **부동산의 추정 시세 점은 표식(속이 빈 원)이다**(009 FR-017, ui-wireframes E6). 점의 선택 키 `estimated`가 참인 점에만, 평가액 선
 * 위에 점만 그리는 시리즈 둘(테두리 색 원 위에 배경색 작은 원)을 겹친다 — 표식이 없으면 넓힌 창의 추정이 그 달의 실거래처럼
 * 보인다. 시세 없음(`no_price`)은 선을 끊고 범례가 그 뜻을 말한다(009 FR-026). 추정 점이 없으면 시리즈를 더 만들지 않는다 —
 * 주식·가상자산·예금은 지금과 같다.
 *
 * **가격 선은 눈금 없는 겹침 축이다**(010 FR-001·FR-004, research R10-7). 주가(원주가 시가)·코인 시세·예금 그 달 발표 금리·부동산 그 달
 * 실거래가 평균을 잔고·수익률과 같은 차트에 그리되, 단위가 달라(종목 통화·시세 통화·연 %·원) 두 축 어느 쪽에도 얹지 않는다 — 잔고
 * 축이면 바닥의 평선, 수익률 축이면 금리를 수익률로 읽는다. `priceScaleId`가 left·right가 아니면 라이브러리가 눈금 없는 겹침 축으로
 * 자동 비율을 준다. 정확한 값은 차트 위 상자로 읽는다. 가격이 없는 점(미발표·결측·거래 없음)에서는 **가격 선만** 끊긴다
 * (`priceSegments` — 직전 값을 끌어오지 않는다). 점 하나뿐인 구간과 부동산(달마다 거래가 드물다)은 점으로 그린다. 잠정 구간은 가격
 * 선도 연한 색이다. 주식 분할은 그린 점 중 효력일 이상인 첫 점에 표식을 단다(`splitMarks` — 원주가가 꺾이는 까닭, FR-008).
 * **점에 `price` 키가 없으면 가격 시리즈를 만들지 않는다** — 005~009의 응답·테스트는 지금과 같다. 기존 테스트 모의 객체에 없는
 * API(`createSeriesMarkers`·`subscribeClick`·`priceScale()`)를 부르지 않는다 — 겹침 축 여백은 `createChart` 옵션으로 준다.
 */

import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { axisPriceFormat, priceSegments, splitMarks, splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import { formatMoney, formatYield } from "@/lib/format";
import type {
  CryptoCollecting,
  DepositCollecting,
  PriceKind,
  RealEstateTradeCollecting,
  SimulationCollecting,
  SimulationPoint,
  SimulationSeriesResponse,
} from "@/lib/types";

/** 잔고는 왼쪽, 수익률은 오른쪽. 축을 섞지 않는 것이 이 컴포넌트의 존재 이유다. */
const BALANCE_AXIS = "left";
const RETURN_AXIS = "right";
/** 가격 선의 겹침 축(010) — left·right가 아니라 눈금이 없다. */
const PRICE_AXIS = "price";

/** 원화·엔화에는 소수점 금액이 없다 — `formatMoney`와 같은 규칙이다. */
const NO_DECIMAL_CURRENCIES = new Set(["KRW", "JPY"]);

/** 선 색. 잠정 구간은 같은 선의 연한 색이다(008). */
const COLORS = {
  confirmed: { balance: "#1f2937", returnRate: "#b45309", price: "#2563eb" },
  provisional: { balance: "#9ca3af", returnRate: "#fcd34d", price: "#93c5fd" },
} as const;

/** 가격 선의 범례 이름(010 FR-005). 단위는 응답의 `priceCurrency`, 예금은 연 %다. */
const PRICE_LABEL: Record<PriceKind, string> = {
  stock_open: "주가",
  crypto_open: "시세",
  deposit_rate: "금리",
  apt_average: "실거래가 평균",
};

/** 분할 표식 — 가격 선 위의 채운 원. */
const SPLIT_MARKER = { color: "#7c3aed", radius: 5 } as const;

/** 추정 표식 — 테두리 원과 그 위의 배경색 작은 원. 둘을 겹쳐 속이 빈 원으로 보인다(라이브러리에 빈 원 모양이 없다). */
const ESTIMATED_MARKER = { ring: 4, hole: 2, holeColor: "#ffffff" } as const;

/**
 * 구간을 확정·잠정으로 나눈다. 경계 점(잠정 시작일)은 양쪽에 둔다 — 선이 이어진다. 확정 쪽이 점 하나뿐이면(처음부터 잠정)
 * 그리지 않는다.
 */
function splitAtProvisional(
  points: SimulationPoint[], from: string | null,
): { points: SimulationPoint[]; tone: keyof typeof COLORS }[] {
  if (from === null) return [{ points, tone: "confirmed" }];
  const confirmed = points.filter((p) => p.date <= from);
  const provisional = points.filter((p) => p.date >= from);
  const parts: { points: SimulationPoint[]; tone: keyof typeof COLORS }[] = [];
  if (confirmed.length > 1) parts.push({ points: confirmed, tone: "confirmed" });
  if (provisional.length > 0) parts.push({ points: provisional, tone: "provisional" });
  return parts;
}

/**
 * 가격 구간을 확정·잠정으로 나눈다(010). 경계 점은 양쪽에 둔다(선이 이어진다). `splitAtProvisional`과 달리 **점 하나뿐인 확정 구간도
 * 남긴다** — 가격은 거래 없는 달 사이의 한 달처럼 점 하나로도 그려야 한다. 확정 쪽이 경계 점 하나뿐이면 잠정 쪽에 이미 있다.
 */
function splitPriceAtProvisional(
  points: SimulationPoint[], from: string | null,
): { points: SimulationPoint[]; tone: keyof typeof COLORS }[] {
  if (from === null) return [{ points, tone: "confirmed" }];
  const confirmed = points.filter((p) => p.date <= from);
  const provisional = points.filter((p) => p.date >= from);
  const parts: { points: SimulationPoint[]; tone: keyof typeof COLORS }[] = [];
  if (confirmed.some((p) => p.date < from)) parts.push({ points: confirmed, tone: "confirmed" });
  if (provisional.length > 0) parts.push({ points: provisional, tone: "provisional" });
  return parts;
}

/** 점을 확정·잠정으로 나눈다 — 표식용이라 경계 점을 겹치지 않는다. 빈 쪽은 뺀다. */
function splitByTone(
  points: SimulationPoint[], from: string | null,
): { points: SimulationPoint[]; tone: keyof typeof COLORS }[] {
  const parts: { points: SimulationPoint[]; tone: keyof typeof COLORS }[] = [
    { points: from === null ? points : points.filter((p) => p.date < from), tone: "confirmed" },
    { points: from === null ? [] : points.filter((p) => p.date >= from), tone: "provisional" },
  ];
  return parts.filter((part) => part.points.length > 0);
}

interface Hover {
  date: string;
  balance: string;
  returnRate: string;
}

export function PerformanceChart({
  series,
  collecting,
  loading,
}: {
  series: SimulationSeriesResponse | null;
  /** 수집 중이면 차트 대신 안내 — 주식(005·006)·가상자산(007)·예금(008)·부동산(009)의 202. */
  collecting: SimulationCollecting | CryptoCollecting | DepositCollecting | RealEstateTradeCollecting | null;
  loading: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  useEffect(() => {
    if (!container.current || series === null || series.points.length === 0) return;

    // 010 — 가격이 있는 응답에만 가격 선(겹침 축)을 만든다. 키가 없으면(005~009) 지금과 같은 차트다.
    const hasPrice = series.points.some((p) => p.price !== undefined);
    const instance = createChart(container.current, {
      height: 360,
      layout: { attributionLogo: false },
      leftPriceScale: { visible: true, borderVisible: false },
      rightPriceScale: { visible: true, borderVisible: false },
      timeScale: { borderVisible: false },
      // 겹침 축의 위아래 여백 — 가격 선이 잔고 선과 차트 끝에 붙지 않게. `priceScale().applyOptions`는 모의 객체에 없다.
      ...(hasPrice ? { overlayPriceScales: { scaleMargins: { top: 0.1, bottom: 0.1 } } } : {}),
    });

    const balanceFormat = axisPriceFormat(NO_DECIMAL_CURRENCIES.has(series.basisCurrency) ? 0 : 2);
    // 이력 비교 차트의 수익률 축과 같은 형식이다(FR-046a) — 같은 화면에서 두 수익률 축이 갈리지 않는다.
    const returnFormat = axisPriceFormat(2);

    const lookup = new Map<string, Hover>();
    for (const p of series.points) {
      lookup.set(p.date, {
        date: p.date, balance: p.balance, returnRate: p.returnRate,
      });
    }

    // 구간마다 두 시리즈 — **잔고와 수익률이 같은 자리에서 함께 끊겨야 한다.**
    // 한쪽만 끊기면 두 선이 다른 구간을 말하게 되고 어느 쪽이 맞는지 알 수 없다.
    const provisionalFrom = series.provisionalFrom ?? null;
    const parts = splitSeriesAtGaps(series.points, series.gaps)
      .flatMap((segment) => splitAtProvisional(segment, provisionalFrom));
    for (const { points: segment, tone } of parts) {
      const balance = instance.addSeries(LineSeries, {
        color: COLORS[tone].balance,
        lineWidth: 2,
        priceScaleId: BALANCE_AXIS,
        priceFormat: balanceFormat,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      balance.setData(
        toPerformanceData(segment, "balance").map((d) => ({
          time: d.time, value: d.value,
        })),
      );

      const profit = instance.addSeries(LineSeries, {
        color: COLORS[tone].returnRate,
        lineWidth: 2,
        lineStyle: 2,
        priceScaleId: RETURN_AXIS,
        priceFormat: returnFormat,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      profit.setData(
        toPerformanceData(segment, "returnRate").map((d) => ({
          time: d.time, value: d.value,
        })),
      );
    }

    // 009 — 추정 시세 점에만 표식. 평가액 축 위에 점만 그리고, 확정·잠정 구간의 선 색을 따른다. 추정 점이 없으면 만들지 않는다.
    const estimated = series.points.filter((p) => p.estimated === true);
    for (const { points: marked, tone } of splitByTone(estimated, provisionalFrom)) {
      for (const [color, radius] of [
        [COLORS[tone].balance, ESTIMATED_MARKER.ring], [ESTIMATED_MARKER.holeColor, ESTIMATED_MARKER.hole],
      ] as const) {
        const marker = instance.addSeries(LineSeries, {
          color,
          lineVisible: false,
          pointMarkersVisible: true,
          pointMarkersRadius: radius,
          priceScaleId: BALANCE_AXIS,
          priceFormat: balanceFormat,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        marker.setData(toPerformanceData(marked, "balance").map((d) => ({ time: d.time, value: d.value })));
      }
    }

    // 010 — 가격 선. 잔고와 같은 자리 + 가격이 없는 점에서 끊고, 잠정은 연한 색. 점 하나 구간과 부동산은 점 표식.
    if (hasPrice) {
      const markersAlways = series.priceKind === "apt_average";
      for (const segment of priceSegments(series.points, series.gaps)) {
        for (const { points: part, tone } of splitPriceAtProvisional(segment, provisionalFrom)) {
          const price = instance.addSeries(LineSeries, {
            color: COLORS[tone].price,
            lineWidth: 2,
            priceScaleId: PRICE_AXIS,
            priceLineVisible: false,
            lastValueVisible: false,
            pointMarkersVisible: markersAlways || part.length === 1,
          });
          price.setData(part.map((p) => ({ time: p.date, value: Number(p.price) })));
        }
      }

      // FR-008 — 분할 표식. 그린 점 중 효력일 이상인 첫 점, 가격 선 위에 점만.
      const priced = new Map(series.points.map((p) => [p.date, p.price]));
      const marks = splitMarks(series.points, series.splits ?? []);
      if (marks.length > 0) {
        const marker = instance.addSeries(LineSeries, {
          color: SPLIT_MARKER.color,
          lineVisible: false,
          pointMarkersVisible: true,
          pointMarkersRadius: SPLIT_MARKER.radius,
          priceScaleId: PRICE_AXIS,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        marker.setData(marks.map((m) => ({ time: m.date, value: Number(priced.get(m.date)) })));
      }
    }

    instance.subscribeCrosshairMove((param) => {
      const time = param.time as string | undefined;
      // 툴팁은 **원본 문자열**을 보여준다. 렌더링용 변환값이 값의 진실이 되면
      // 정밀도가 손실된 값을 사용자가 보게 된다.
      setHover(time ? (lookup.get(time) ?? null) : null);
    });

    instance.timeScale().fitContent();
    return () => {
      instance.remove();
    };
  }, [series]);

  if (collecting) {
    return (
      <p role="status" className="py-12 text-center text-sm text-gray-600">
        아직 받지 못한 구간이 있어 수집을 시작했습니다. 완료되면 차트가 표시됩니다.
      </p>
    );
  }
  if (loading || series === null) {
    return <p className="py-12 text-center text-sm text-gray-500">불러오는 중…</p>;
  }
  if (series.points.length === 0) {
    return <p className="py-12 text-center text-sm text-gray-500">표시할 구간이 없습니다.</p>;
  }

  // 휴장일 구간은 세지 않는다 — 이어 그리는 구간을 "없음"이라 부르면 화면과 말이
  // 어긋난다. 선은 이어져 있는데 범례만 비었다고 말하게 된다 (001 T124).
  const notCollected = series.gaps.filter((g) => g.reason === "not_collected").length;
  // 007 FR-023 — 가상자산의 출처 결측. 선이 끊긴 이유를 범례가 말한다(ui-wireframes C5).
  const missing = series.gaps.filter((g) => g.reason === "source_missing").length;
  // 009 — 부동산의 시세 없음(끊음)과 추정 시세 표식.
  const noPrice = series.gaps.some((g) => g.reason === "no_price");
  const hasEstimated = series.points.some((p) => p.estimated === true);
  // 010 — 가격 선의 이름과 단위(FR-005). 단위가 없으면 USD 시세를 KRW 잔고와 같은 통화로 읽는다.
  const priceLegend = series.priceKind !== undefined && series.points.some((p) => p.price !== undefined)
    ? `${PRICE_LABEL[series.priceKind]} (${series.priceKind === "deposit_rate" ? "연 %" : (series.priceCurrency ?? "")})`
    : null;
  const hasSplitMark = priceLegend !== null && splitMarks(series.points, series.splits ?? []).length > 0;

  return (
    <section className="rounded-lg border border-gray-200 p-4">
      <div ref={container} data-testid="performance-canvas" />

      {hover && (
        <div
          data-testid="performance-tooltip"
          className="mt-3 inline-flex items-center gap-4 rounded border border-gray-200 px-3 py-2 text-sm"
        >
          <span className="text-gray-500">{hover.date}</span>
          <span className="tabular-nums font-medium">
            {formatMoney(hover.balance, series.basisCurrency)}{" "}
            {series.basisCurrency}
          </span>
          <span className="tabular-nums text-amber-700">
            {formatYield(hover.returnRate)}
          </span>
        </div>
      )}

      <footer
        data-testid="chart-legend"
        className="mt-4 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-500"
      >
        {/* FR-041 — 기준 통화를 밝히지 않으면 어느 통화를 보는지 알 수 없다. */}
        <span>─ 잔고 ({series.basisCurrency})</span>
        <span className="text-amber-700">╌ 수익률 (%)</span>
        {priceLegend !== null && <span className="text-blue-600">─ {priceLegend}</span>}
        {hasSplitMark && <span className="text-violet-600">● 분할</span>}
        {notCollected > 0 && <span>╌╌ 미수집 {notCollected}구간</span>}
        {missing > 0 && <span>┆ 결측 {missing}구간</span>}
        {hasEstimated && <span>○ 추정 시세(1개월 밖의 창)</span>}
        {noPrice && <span>⋯ 시세 없음(끊음)</span>}
        {/* 008 — 잠정 금리로 계산한 구간. 연한 색 선이 무엇인지 범례가 말한다. */}
        {series.provisionalFrom != null && (
          <span className="text-gray-400">┄ 잠정({series.provisionalFrom}부터)</span>
        )}
        <span className="ml-auto">
          {series.downsampled
            ? `원본 ${series.sourcePointCount.toLocaleString()}개 중 ${series.points.length.toLocaleString()}개 (${series.algorithm.toUpperCase()})`
            : `${series.points.length.toLocaleString()}개 전부 표시`}
        </span>
      </footer>
    </section>
  );
}
