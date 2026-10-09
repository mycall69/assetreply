/**
 * 지표 화면 `/dashboard/{지표}?unit=` (014 T061) — FR-010, FR-011, research R14-14.
 *
 * 서버 컴포넌트가 `params`·`searchParams`(Next 16에서 Promise)를 풀어 클라이언트 부품에 넘긴다 — `useSearchParams`의 Suspense
 * 경계가 필요 없다. 틀리거나 없는 단위는 `daily`다. 없는 지표는 서버 경로의 404를 받아 화면이 안내한다.
 */
import { IndicatorView } from "@/components/dashboard/IndicatorView";
import type { IndicatorUnit } from "@/lib/types";

const UNITS: readonly IndicatorUnit[] = ["daily", "weekly", "monthly", "yearly"];

export default async function IndicatorPage({ params, searchParams }: {
  params: Promise<{ indicator: string }>;
  searchParams: Promise<{ unit?: string | string[] }>;
}) {
  const { indicator } = await params;
  const query = await searchParams;
  const raw = Array.isArray(query.unit) ? query.unit[0] : query.unit;
  const unit = UNITS.find((u) => u === raw) ?? "daily";
  return <IndicatorView id={indicator} unit={unit} />;
}
