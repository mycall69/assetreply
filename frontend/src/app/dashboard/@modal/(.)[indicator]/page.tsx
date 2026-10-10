/**
 * 가로챈 지표 모달 (014 반복 2026-10-10b T122) — FR-010, research R14-20.
 *
 * 대시보드 안에서 카드를 누르면 이 경로가 지표 주소를 가로채 대시보드 위에 모달을 띄운다. 닫기는 `router.back()`이다(브라우저 뒤로와
 * 같다). 서버 컴포넌트가 `params`·`searchParams`(Next 16에서 Promise)를 풀어 넘긴다 — 틀리거나 없는 기간은 1년이다.
 */
import { IndicatorModal } from "@/components/dashboard/IndicatorModal";
import { rangeOf } from "@/components/dashboard/RangePicker";

export default async function InterceptedIndicator({ params, searchParams }: {
  params: Promise<{ indicator: string }>;
  searchParams: Promise<{ range?: string | string[] }>;
}) {
  const { indicator } = await params;
  const query = await searchParams;
  return <IndicatorModal id={indicator} range={rangeOf(query.range)} mode="intercepted" />;
}
