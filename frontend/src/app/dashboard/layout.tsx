/**
 * 대시보드 배치 (014 반복 2026-10-10b T122) — FR-010, research R14-20.
 *
 * 대시보드(`children`)와 지표 모달 슬롯(`modal`)을 함께 그린다. 카드를 누르면(대시보드 안 이동) `@modal/(.)[indicator]`가 지표 경로를
 * 가로채 대시보드 위에 모달을 띄운다 — 주소는 `/dashboard/{지표}?range=`라 공유·새로고침이 된다. 새로고침·주소 직접 입력은 가로채지
 * 않고 `[indicator]/page.tsx`가 대시보드와 같은 모달을 그린다.
 */
export default function DashboardLayout({ children, modal }: { children: React.ReactNode; modal: React.ReactNode }) {
  return (
    <>
      {children}
      {modal}
    </>
  );
}
