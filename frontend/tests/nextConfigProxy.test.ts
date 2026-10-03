/**
 * 백엔드 API 프록시 (T109) — 버그 `stock-search-not-found`, 006 tasks T109·T110.
 *
 * **브라우저의 `/api/*` 요청은 Next.js의 rewrite를 거쳐야 백엔드에 닿는다**(`next.config.ts`). 규칙이 빠진
 * 경로는 Next.js가 직접 받아 HTML 404를 돌려주고, `apiClient`는 그것을 "Not Found"로 보인다. 001이 `/api/fx`
 * 규칙만 만들었고 005가 `/api/stocks`를 더하면서 규칙을 빠뜨려, **주식 화면 전체가 브라우저에서 한 번도 동작하지
 * 않았다.** 다른 프론트엔드 테스트는 모두 `apiClient`를 흉내 내어 프록시를 거치지 않으므로 이 테스트만 잡는다.
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import nextConfig from "../next.config";

interface Rule {
  source: string;
  destination: string;
}

async function rules(): Promise<Rule[]> {
  const rewrites = await nextConfig.rewrites?.();
  if (rewrites === undefined) return [];
  if (Array.isArray(rewrites)) return rewrites;
  return [...(rewrites.beforeFiles ?? []), ...(rewrites.afterFiles ?? []),
    ...(rewrites.fallback ?? [])];
}

/** Next.js 경로 패턴(`/api/:path*`)이 경로를 덮는지. 이 저장소가 쓰는 두 꼴(`:name`·`:name*`)만 다룬다. */
function matches(source: string, pathname: string): boolean {
  const pattern = source
    .replace(/[.+?^${}()|[\]\\]/g, "\\$&")
    .replace(/\/:[A-Za-z]+\*/g, "(?:/.*)?")
    .replace(/:[A-Za-z]+/g, "[^/]+");
  return new RegExp(`^${pattern}$`).test(pathname);
}

/** 경로를 덮고, **같은 경로 그대로 바깥(백엔드)으로** 넘기는 규칙. */
function proxyFor(all: Rule[], pathname: string): Rule | undefined {
  return all.find((rule) => matches(rule.source, pathname)
    && /^https?:\/\//.test(rule.destination)
    && rule.destination.endsWith(rule.source));
}

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return sourceFiles(full);
    return /\.(ts|tsx)$/.test(name) ? [full] : [];
  });
}

describe("백엔드 API 프록시", () => {
  it.each([
    "/api/stocks/search",
    "/api/stocks/search/external",
    "/api/stocks/selection",
    "/api/stocks/simulation",
    "/api/stocks/simulation/series",
    "/api/stocks/progress",
    "/api/stocks/settings",
    "/api/fx/latest",
    "/api/fx/collection/stream",
  ])("%s를 백엔드로 넘긴다", async (pathname) => {
    expect(proxyFor(await rules(), pathname)).toBeDefined();
  });

  it("프론트엔드 소스가 부르는 모든 /api 접두사를 넘긴다", async () => {
    // 새 자산군이 접두사를 더하고 규칙을 빠뜨리면 여기서 걸린다 — 005가 그랬다.
    const prefixes = new Set<string>();
    for (const file of sourceFiles(join(__dirname, "..", "src"))) {
      for (const found of readFileSync(file, "utf-8").matchAll(/\/api\/[a-z][a-z-]*/g)) {
        prefixes.add(found[0]);
      }
    }
    expect([...prefixes].sort()).toEqual(expect.arrayContaining(["/api/fx", "/api/stocks"]));
    const all = await rules();
    const missing = [...prefixes].filter((prefix) => proxyFor(all, `${prefix}/x`) === undefined);
    expect(missing).toEqual([]);
  });
});
