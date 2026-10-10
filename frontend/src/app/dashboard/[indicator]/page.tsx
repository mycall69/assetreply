/**
 * 지표 주소 `/dashboard/{지표}?range=` — 직접 연 모달 (014 T061 → 반복 2026-10-10b T122) — FR-010, FR-011, research R14-14·R14-20.
 *
 * 새로고침·주소 직접 입력·즐겨찾기는 가로채지 않으므로 이 경로다 — 대시보드 위에 같은 모달을 그린다(지표만의 화면은 없다). 닫기는
 * `/dashboard`로 바꾼다(뒤로 가면 사이트 밖일 수 있다). 서버 컴포넌트가 `params`·`searchParams`(Next 16에서 Promise)를 풀어 넘긴다 —
 * 틀리거나 없는 기간은 1년이다(옛 `unit` 주소도). 없는 지표는 서버 경로의 404를 받아 모달이 안내한다.
 */
import DashboardPage from "@/app/dashboard/page";
import { IndicatorModal } from "@/components/dashboard/IndicatorModal";
import { rangeOf } from "@/components/dashboard/RangePicker";

export default async function IndicatorPage({ params, searchParams }: {
  params: Promise<{ indicator: string }>;
  searchParams: Promise<{ range?: string | string[] }>;
}) {
  const { indicator } = await params;
  const query = await searchParams;
  return (
    <>
      <DashboardPage />
      <IndicatorModal id={indicator} range={rangeOf(query.range)} mode="direct" />
    </>
  );
}
