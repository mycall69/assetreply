/**
 * 성과 표와 최근 시뮬레이션의 배치 (010 T034) — FR-015~FR-017, research R10-10, data-model 6절, ui-wireframes F3.
 *
 * **경계 폭을 상수로 두지 않는다.** 줄바꿈 flex에서 표 칸은 `flex: 0 1 auto`(기본 크기 = 표 고유 폭, 늘지 않는다), 이력 칸은 `flex: 1 1
 * 400px`(남는 폭을 가져간다)이다. 두 칸의 기본 크기 합이 본문 폭 이하면 나란히 — 이력이 표 바로 오른쪽에 붙는다(표 칸이 늘면 표와 이력
 * 사이에 빈 칸이 생겨 이력이 화면 끝에 붙는다 — T036 실측) — 넘으면 이력이 다음 줄(전체 폭)로 내려간다. 자산군·조건마다 표의 열이 달라도(배당 열, 환산 열)
 * 그 표의 실제 폭으로 경계가 정해진다 — 고정 경계는 열이 바뀌면 조용히 틀린다(너무 좁으면 열이 잘리고, 너무 넓으면 흔한 창에서 늘 아래로
 * 내려간다 — FR-015의 두 실패 양상).
 *
 * 표 칸의 `min-w-0`: 줄을 나누는 것은 기본 크기라 나란히 둔 표는 줄지 않는다. 창이 표 하나도 담지 못할 때(1440px 미만)는 지금처럼 표 안에서
 * 가로 스크롤한다 — 없으면 표 칸이 표 고유 폭 아래로 줄지 않아 화면 전체가 가로로 넘친다(표 부품이 `overflow-x-auto` 안에 있다).
 *
 * 이력 칸은 sticky라 긴 표를 내려도 화면에 남고(FR-016), 이력이 길면 칸 안에서 세로 스크롤한다. 결과가 없으면 이력 칸만이다(전체 폭).
 * 이력 비교 차트는 이 부품 밖 — 아래 전체 폭이다(FR-017). 네 화면이 이 부품 하나를 쓴다 — 한 화면만 다르게 고쳐지는 일을 막는다.
 */
import type { ReactNode } from "react";

export function TableWithHistory({ table, history }: { table: ReactNode | null; history: ReactNode }) {
  return (
    <div data-testid="table-with-history" className="flex flex-wrap items-start gap-5">
      {table !== null && <div className="min-w-0 flex-[0_1_auto]">{table}</div>}
      <aside className="sticky top-4 max-h-[calc(100vh-2rem)] flex-[1_1_400px] self-start overflow-y-auto">
        {history}
      </aside>
    </div>
  );
}
