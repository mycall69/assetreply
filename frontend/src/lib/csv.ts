/**
 * 일자별 상세 CSV 조립 (T072) — FR-044~047, research R2-7.
 *
 * **`Number()`·`parseFloat()`를 쓰지 않는다.** 서버가 이미 `Decimal`로 산출해 문자열로
 * 내려준 값을 그대로 이어 붙인다. 한 번이라도 숫자로 변환하면 IEEE 754를 거치며
 * 정밀도가 손실되고, 헌법 원칙 VI가 파일 출력 단계에서 무너진다.
 *
 * 표시용 형식(1,354.20)이 아니라 **원본 정밀도 문자열**을 담는다 (FR-045).
 */

import type { DailyResponse } from "./types";

const HEADER = "날짜,매매기준율,현금 살 때,현금 팔 때,송금 보낼 때,송금 받을 때,확정 여부";

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
    `# 구간,${last} ~ ${first}`,
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
