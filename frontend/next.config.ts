import type { NextConfig } from "next";

/**
 * 백엔드 주소. 프록시 목적지로만 쓰이며 **브라우저에 노출되지 않는다**
 * (`NEXT_PUBLIC_` 접두사가 없으므로 서버에서만 읽힌다).
 *
 * `BE_PORT`는 be-start.sh가 쓰는 것과 같은 환경변수다. 한 곳만 바꾸면 스크립트와
 * 프록시가 함께 따라오도록 이름을 맞췄다.
 */
const backendUrl =
  process.env.BACKEND_URL ?? `http://localhost:${process.env.BE_PORT ?? 8080}`;

const nextConfig: NextConfig = {
  /**
   * 백엔드 API를 같은 출처로 프록시한다.
   *
   * 프론트엔드(3030)와 백엔드(8080)는 포트가 달라 브라우저 기준 교차 출처다.
   * 절대 URL로 직접 호출하면 CORS에 막히므로, rewrite로 동일 출처를 만들어
   * 프리플라이트와 CORS 설정 자체를 없앤다.
   *
   * 백엔드에 CORS를 여는 대신 이 방식을 택한 이유:
   * - 허용 출처 목록을 환경마다 관리하지 않아도 된다
   * - `EventSource`(SSE)는 CORS 설정이 까다롭고 커스텀 헤더를 붙일 수 없다.
   *   동일 출처면 이 문제가 사라진다 (contracts/sse-progress.md)
   *
   * **`/api/*` 전체를 넘긴다.** 자산군마다 접두사를 더하는 구조였을 때 005가 `/api/stocks`를
   * 빠뜨려, 주식 화면의 모든 요청이 Next.js의 404("Not Found")가 되었다(버그
   * `stock-search-not-found`). 프론트엔드에는 API 라우트 핸들러가 없고, 배열로 돌려준 rewrite는
   * 화면·정적 파일을 먼저 확인한 뒤(afterFiles) 적용되어 화면 경로와 부딪히지 않는다.
   * `tests/nextConfigProxy.test.ts`가 소스가 쓰는 모든 `/api` 접두사가 넘어가는지 검사한다.
   */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
