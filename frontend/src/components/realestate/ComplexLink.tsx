"use client";

/**
 * 부동산 단지 이름 링크 (010 반복 3, T066) — FR-029, FR-026(물러남), ui-wireframes F5 보탬.
 *
 * 처음부터 링크가 있다 — 네이버 검색(법정동 이름과 단지명)으로 시작하고, 단지 번호를 찾으면 Npay 부동산의 그 단지 화면이 된다.
 * 못 찾음·실패는 검색 그대로다. 겉모습은 같고 접근 이름이 어디로 가는지 밝힌다.
 */

import { ExternalLink } from "@/components/ExternalLink";
import { complexSearchLink } from "@/lib/externalLinks";
import { useNaverComplexHref } from "@/lib/naverComplexLink";

export function ComplexLink({ complexId, name, umdName }: { complexId: number; name: string; umdName: string | null }) {
  const direct = useNaverComplexHref(complexId);
  return (
    <ExternalLink href={direct ?? complexSearchLink(name, umdName)}
      label={direct !== null ? `${name} Npay 부동산에서 보기` : `${name} 네이버에서 단지 찾기`}>
      {name}
    </ExternalLink>
  );
}
