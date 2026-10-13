/**
 * 투자 성과표의 등락 두 칸 (014 반복 2026-10-13b T225) — spec FR-047, contracts D20.
 *
 * 주식·가상자산 일시금·적립식 네 표가 가격 열마다 바로 뒤에 둔다. 값은 서버가 `Decimal`로 낸 글자(FR-048)이고 여기서는 기호·색·부호만 입힌다 —
 * 숫자로 바꿔 계산하지 않는다(헌법 원칙 VI). 기호·색은 외환 표와 같은 값(`lib/changeStyle`)이다.
 *
 * - 등락폭은 크기만(방향은 기호가) 그 가격 열과 같은 형식 — 주식 `formatRate`, 가상자산 `formatPrice`(유효 숫자)
 * - 칸 `title`은 비교한 날짜 — 주·월 표·사건 행에서 어느 행과 견줬는지 알 수 있다
 * - 분할을 맞춘 칸은 ✂ — 기호만으로 전하지 않는다(이름·`title`, 006 FR-041c의 📅와 같은 꼴)
 * - 비교할 행이 없으면(키가 없거나 `null`) 두 칸 "—", 비율만 없으면 등락률만 "—" — 0으로 메우지 않는다(원칙 V)
 */
import { ARROW, TONE } from "@/lib/changeStyle";
import type { PriceChange } from "@/lib/types";

export function PriceChangeCells({ change, format, cell }: {
  change: PriceChange | null | undefined;
  /** 등락폭 형식 — 그 가격 열과 같은 함수. */
  format: (value: string) => string;
  /** 칸 클래스 — 표마다의 여백·정렬. */
  cell: string;
}) {
  if (change == null) {
    return (
      <>
        <td className={`${cell} text-gray-500`}>—</td>
        <td className={`${cell} text-gray-500`}>—</td>
      </>
    );
  }
  const tone = TONE[change.direction];
  const title = `${change.comparedTo} 대비`;
  const percent = change.percent === null ? "—" : `${change.direction === "up" ? "+" : ""}${change.percent}%`;
  const split = change.split === null ? null : `${change.split.ratio} 분할 반영 — 직전 값을 분할 비율로 맞춰 견줬습니다`;
  return (
    <>
      <td className={`whitespace-nowrap ${cell} ${tone}`} title={title}>
        {`${ARROW[change.direction]}${format(change.absolute.replace(/^-/, ""))}`}
        {split !== null && (
          <span role="img" className="ml-0.5" title={split} aria-label={split}>✂</span>
        )}
      </td>
      <td className={`${cell} ${tone}`} title={title}>{percent}</td>
    </>
  );
}

/**
 * 머리글 이름 — 등락 열("시작가 등락폭"·"종가 등락률"·"시가 등락폭")은 보이는 글자가 "등락폭"·"등락률"이고 앞의 가격은 화면 읽기 이름에만 있다
 * (주식 표에 같은 이름이 둘이다 — FR-047 실패 양상). 다른 열은 그대로다.
 */
export function ColumnName({ name }: { name: string }) {
  const match = /^(.+) (등락폭|등락률)$/.exec(name);
  if (match === null) return <>{name}</>;
  // 사이 공백은 숨은 글자 밖에 둔다 — 안에 두면 이름 계산이 그 공백을 버려 "시작가등락폭"이 된다. 밖의 공백은 줄 머리라 보이지 않는다.
  return (
    <>
      <span className="sr-only">{match[1]}</span>
      {" "}
      {match[2]}
    </>
  );
}

/** 날짜 칸 고정(FR-047) — 표를 가로로 밀어도 왼쪽에 남는다. 배경이 불투명해야 밀린 칸이 비쳐 보이지 않는다(행 색이 있으면 그 색을 준다). */
export const STICKY = "sticky left-0 z-[1]";
/** 행 색이 없는 날짜 칸·머리 칸. */
export const STICKY_DATE = `${STICKY} bg-white`;
