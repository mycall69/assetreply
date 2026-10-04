# Specification Quality Checklist: 예금 투자 시뮬레이션

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-04
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

- 1회 검증에서 한 건을 고쳤다 — FR-014의 "설정(.env)"을 "설정"으로(구현 세부).
- 출처 이름(한국은행 ECOS)과 통계 이름(예금은행·비은행금융기관 가중평균 금리, 신규취급액 기준)은 사용자가 정한 **업무 요구**라 남겼다.
  통계표·항목 코드, 호출 한도, 발표 시점, 과거 값 수정 여부는 plan 단계에서 실측한다.
- `[NEEDS CLARIFICATION]` 표시를 두지 않았다. 사용자가 `/speckit-clarify`에서 정하겠다고 한 열린 질문은 실행 가능한 기본값으로 명세에 넣고,
  Assumptions에 "(clarify에서 확인)"으로 표시했다:
  - 원 단위 처리(이자·세금 원 미만 버림)
  - 경과 이자 평가(만기 전 잔고 = 예치 원금 + 세후 경과 이자, 일할)
  - 재예치 금리가 없을 때(만기일에서 계산을 멈추고 알린다)
  - 표의 행 기준일(가입 행·매달 1일 행·만기 행·재예치 행)
- 조합원 저율과세(투자처별 세율)는 요청대로 Out of Scope다(세율은 설정 하나).
