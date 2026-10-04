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
 */

import { useEffect, useRef, useState } from "react";
import { createChart, LineSeries } from "lightweight-charts";
import { splitSeriesAtGaps, toPerformanceData } from "@/lib/chartSeries";
import { formatMoney, formatYield } from "@/lib/format";
import type { CryptoCollecting, SimulationCollecting, SimulationSeriesResponse } from "@/lib/types";

/** 잔고는 왼쪽, 수익률은 오른쪽. 축을 섞지 않는 것이 이 컴포넌트의 존재 이유다. */
const BALANCE_AXIS = "left";
const RETURN_AXIS = "right";

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
  /** 수집 중이면 차트 대신 안내 — 주식(005·006)과 가상자산(007)의 202. */
  collecting: SimulationCollecting | CryptoCollecting | null;
  loading: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<Hover | null>(null);

  useEffect(() => {
    if (!container.current || series === null || series.points.length === 0) return;

    const instance = createChart(container.current, {
      height: 360,
      layout: { attributionLogo: false },
      leftPriceScale: { visible: true, borderVisible: false },
      rightPriceScale: { visible: true, borderVisible: false },
      timeScale: { borderVisible: false },
    });

    const lookup = new Map<string, Hover>();
    for (const p of series.points) {
      lookup.set(p.date, {
        date: p.date, balance: p.balance, returnRate: p.returnRate,
      });
    }

    // 구간마다 두 시리즈 — **잔고와 수익률이 같은 자리에서 함께 끊겨야 한다.**
    // 한쪽만 끊기면 두 선이 다른 구간을 말하게 되고 어느 쪽이 맞는지 알 수 없다.
    for (const segment of splitSeriesAtGaps(series.points, series.gaps)) {
      const balance = instance.addSeries(LineSeries, {
        color: "#1f2937",
        lineWidth: 2,
        priceScaleId: BALANCE_AXIS,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      balance.setData(
        toPerformanceData(segment, "balance").map((d) => ({
          time: d.time, value: d.value,
        })),
      );

      const profit = instance.addSeries(LineSeries, {
        color: "#b45309",
        lineWidth: 2,
        lineStyle: 2,
        priceScaleId: RETURN_AXIS,
        priceLineVisible: false,
        lastValueVisible: false,
      });
      profit.setData(
        toPerformanceData(segment, "returnRate").map((d) => ({
          time: d.time, value: d.value,
        })),
      );
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
        {notCollected > 0 && <span>╌╌ 미수집 {notCollected}구간</span>}
        {missing > 0 && <span>┆ 결측 {missing}구간</span>}
        <span className="ml-auto">
          {series.downsampled
            ? `원본 ${series.sourcePointCount.toLocaleString()}개 중 ${series.points.length.toLocaleString()}개 (${series.algorithm.toUpperCase()})`
            : `${series.points.length.toLocaleString()}개 전부 표시`}
        </span>
      </footer>
    </section>
  );
}
