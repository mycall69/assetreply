# Specification Quality Checklist: 대시보드 — 오늘의 시장 지표 15개와 과거 추이, 세 나라의 경제 뉴스

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-09
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- 검증 1회차(2026-10-09)에 모든 항목이 통과했다.
- **구현 세부 항목**: 명세에 나오는 `source`·`ingested_at`·UTC 저장·원본/정규화 분리는 헌법 원칙 V의 시계열 불변식을 옮긴 것이다. ECOS·001·012 같은 이름은 기존 기능의
  규칙을 가리킨다. 둘 다 001~013 명세와 같은 관례이며, 언어·프레임워크·엔드포인트를 정하지 않는다. 지표 출처와 표시 방식(모달 등)은 plan에서 정한다.
  - 코드 심볼 하나(`collection_gate`)는 1회차에 "006의 수집 요청 관문"으로 바꿨다
- **[NEEDS CLARIFICATION] 없음**: 결정 후보 여섯은 근거 있는 기본값을 Assumptions에 적었다 — 그래프 단위의 뜻, 장중 값과 새로 받는 주기, 환율 출처, 뉴스의 "오늘의" 기준과 캐시,
  히스토리 범위. `/speckit-clarify`에서 다시 확인할 것을 권한다. 특히 둘은 틀리면 설계가 크게 바뀐다.
  - **그래프 "일·주·월·년"의 뜻**: 기본값은 점의 기간 단위다(FR-011). 보는 범위로 읽으면 설계가 달라진다
  - **환율 출처**: 기본값은 001의 ECOS 매매기준율이다(FR-018). 시장 실시간 환율로 읽으면 새 출처가 생긴다
- **원칙 II 이탈 후보**: 뉴스 세 사이트의 스크래핑, 그리고 지표 출처가 비공식 경로일 경우는 plan의 Complexity Tracking에서 약관·robots.txt를 확인하고 사용자 승인을 받는다.
  이 작업은 명세 범위 밖이며 plan의 게이트다.
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
