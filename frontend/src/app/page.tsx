/**
 * 최상위 주소 (014 T040) — FR-001, research R14-14.
 *
 * 앱을 처음 여는 주소는 대시보드로 옮긴다. 대시보드를 `/`에 두지 않는 까닭은 사이드바의 선택 판정이 경로 앞부분 일치라
 * `href: "/"`면 모든 화면에서 "대시보드"가 선택되기 때문이다(FR-001 실패 양상).
 */
import { redirect } from "next/navigation";

export default function Home() {
  redirect("/dashboard");
}
