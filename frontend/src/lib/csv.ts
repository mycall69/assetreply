/**
 * 일자별 상세 CSV 조립 (T072) — FR-044~047, research R2-7.
 *
 * **`Number()`·`parseFloat()`를 쓰지 않는다.** 서버가 이미 `Decimal`로 산출해 문자열로
 * 내려준 값을 그대로 이어 붙인다. 한 번이라도 숫자로 변환하면 IEEE 754를 거치며
 * 정밀도가 손실되고, 헌법 원칙 VI가 파일 출력 단계에서 무너진다.
 *
 * 표시용 형식(1,354.20)이 아니라 **원본 정밀도 문자열**을 담는다 (FR-045).
 */

import type { DailyResponse, PeriodUnit } from "./types";

// 014 반복 2026-10-10d(FR-031) — 등락 두 열은 **맨 끝**이다. 앞에 끼우면 전에 받은 파일을 읽던 도구가 열을 잘못 읽는다.
const HEADER =
  "날짜,매매기준율,현금 살 때,현금 팔 때,송금 보낼 때,송금 받을 때,확정 여부," +
  "원래 기준일,진행 중,등락폭,등락율";

/** 파일만 봐도 어느 단위인지 알아야 한다 (FR-016a). */
const UNIT_NAME: Record<PeriodUnit, string> = {
  daily: "일별", weekly: "주별", monthly: "월별",
};

/** 쉼표·따옴표·줄바꿈이 있으면 따옴표로 감싸고 내부 따옴표를 겹친다 (RFC 4180). */
function quote(value: string): string {
  return /[",\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

export function buildDailyCsv(data: DailyResponse): string {
  const first = data.rows.at(0)?.date ?? "";
  const last = data.rows.at(-1)?.date ?? "";
  const s = data.appliedSpread;

  const preamble = [
    `# 통화,${data.currency}`,
    `# 기간 단위,${UNIT_NAME[data.period]}`,
    // FR-016c: 담긴 범위를 밝힌다. 밝히지 않으면 사용자는 표 전체를 받았다고 믿는다 —
    // 3페이지를 훑고 90행을 받았는데 그것이 60년치라고 오해한다.
    `# 담긴 범위,${last} ~ ${first} (${data.rows.length}행)`,
    "# 화면에 쌓인 행만 담깁니다. 더 받으려면 표를 더 내려본 뒤 다시 내려받으세요.",
    `# 적용 스프레드(현금 살 때),${s.cashBuy}`,
    `# 적용 스프레드(현금 팔 때),${s.cashSell}`,
    `# 적용 스프레드(송금 보낼 때),${s.remitSend}`,
    `# 적용 스프레드(송금 받을 때),${s.remitReceive}`,
    "# 파생 환율은 현재 스프레드를 각 날짜에 적용한 가정입니다. 실측값은 매매기준율뿐입니다.",
  ];

  const rows = data.rows.map((r) =>
    [
      r.date,
      r.baseRate,
      r.derived.cashBuy,
      r.derived.cashSell,
      r.derived.remitSend,
      r.derived.remitReceive,
      r.isProvisional ? "잠정" : "확정",
      // FR-016b: 표시가 파일에서 빠지면 화면에서 막은 오해가 파일에서 되살아난다.
      // 파일만 본 사람은 2026-07-16을 그냥 7월 데이터로 읽는다.
      r.shiftedFrom ?? "",
      r.isOngoing ? "예" : "아니오",
      // 서버 글자 그대로(기호·`%` 없음). 비교할 행이 없으면 빈 칸이다 — 0으로 메우지 않는다.
      r.change?.absolute ?? "",
      r.change?.percent ?? "",
    ]
      .map(quote)
      .join(","),
  );

  return [...preamble, HEADER, ...rows].join("\n");
}

/** 브라우저에서 파일로 내려받는다. */
export function downloadCsv(filename: string, content: string): void {
  // BOM을 앞에 붙여 스프레드시트가 UTF-8로 열도록 한다.
  const blob = new Blob([`﻿${content}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
