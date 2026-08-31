/**
 * 대시보드 자리 (T016) — research R2-10.
 *
 * 자산군을 하나씩 완결하는 헌법 원칙 IX에 따라 대시보드는 아직 만들지 않는다.
 * 사이드바에서 이 항목은 선택할 수 없으나, 최상위 경로로 들어온 사용자가 빈 화면을
 * 만나지 않도록 안내를 둔다.
 */

import Link from "next/link";

export default function DashboardPlaceholder() {
  return (
    <section className="mx-auto max-w-lg py-20 text-center">
      <h2 className="text-lg font-semibold text-gray-900">대시보드는 준비 중입니다</h2>
      <p className="mt-2 text-sm text-gray-600">
        자산군을 하나씩 완결하며 넓혀가고 있습니다. 현재는 외환을 이용할 수 있습니다.
      </p>
      <Link
        href="/fx"
        className="mt-6 inline-block rounded bg-gray-900 px-5 py-2 text-sm text-white"
      >
        외환으로 이동
      </Link>
    </section>
  );
}
