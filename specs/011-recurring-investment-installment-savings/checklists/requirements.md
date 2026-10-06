# Specification Quality Checklist: 주식·가상자산 적립식 투자, 예금 정기 적금, 주식 매도 세금 설정

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-06
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

- 검증 1회차(2026-10-06): 미정 사항 두 곳(FR-026 첫 적금 뒤의 새 돈, FR-037 법령 표와 설정의 관계)이 남아 사용자에게 물었다.
- 검증 2회차(2026-10-06): 답을 반영했다 — 적금은 "만기 금액 → 정기예금, 월 납입액 → 새 적금, 1년 뒤 두 만기 금액을 합쳐 다시 정기예금"(US3,
  FR-023~FR-032, Key Entities, SC-001·SC-005, Edge Cases, Assumptions), 세율은 "설정이 표를 대체"(FR-037·FR-039, Edge Cases). 표식 0개, 모든
  항목 통과.
- 구현 세부 판정: ECOS 통계표·스프레드 우대·의제 취득가 같은 말은 도메인 용어(출처와 세법)로 보고 구현 세부에서 뺐다 — 005~010 명세와 같은 기준이다.
  코드 심볼·엔드포인트·저장 형식은 쓰지 않았다.
- 실패 양상: 명세 작성 규약에 따라 판정이 갈리는 요구사항(FR-002~FR-005, FR-007, FR-008, FR-010~FR-013, FR-016, FR-020, FR-025, FR-026,
  FR-029, FR-036, FR-037)에 실패 양상을 함께 적었다.
- 기존 검사 변경 예정 1건: 010 반복 4의 "세율 표 밖 기준일은 세금을 비운다"(FR-037) — 구현 때 사용자 승인을 받는다(헌법 원칙 III).
- 남은 판단(기본값으로 정함, `/speckit-clarify`에서 바꿀 수 있음): 매주·매년 납입일의 기준(주의 첫 거래일·시작 월), 단순 수익률, 가상자산 세금 0(2027
  시행 전).
- plan 단계 반영(2026-10-06): ECOS 실측(적금은 시중은행·상호금융만), 계산 끝 뒤로 미뤄진 납입, 같은 날 행은 따로, 적금 경과 평가 식 — FR-004·FR-014·
  FR-019·FR-023·FR-028·FR-029·FR-032, Edge Cases, Assumptions. 항목 판정은 그대로 통과다.
- 분석 반영(2026-10-06): B1(재투자 켬의 배당은 재투자일까지 배당 현금) 등 9건 — spec Iterations. 항목 판정은 그대로 통과다.
