# Specification Quality Checklist: 주식 시뮬레이션 개선 — 시작일·종목 검색·환전

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-02
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

- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
- **[NEEDS CLARIFICATION] 3건 해소 (2026-10-02)**: Q1 A — 국내 목록에 ETF·리츠 포함, ETN 제외
  (FR-010·010a). Q2 B — 원금 통화는 원화 또는 종목 통화만, 교차 조합은 막는다(FR-050~050d).
  Q3 A — 환전 기준일은 실제 첫 매수일(FR-041). spec.md의 Clarifications에 기록했다.
- **Q2의 귀결**: 지원 시장에 유로로 거래되는 종목이 없어 유로 원금은 선택지에서 빠진다
  (FR-050d). 005 시절 이력의 해당 항목은 지우지 않는다(FR-050c).
- **"구현 세부 없음" 판단 근거**: 출처 이름(키움증권 REST API)은 사용자가 지정한 업무 제약이라
  요구사항과 Dependencies에 둔다. 출처의 API 식별자·필드명·호출 경로는 명세에 넣지 않았다
  (설계 단계의 몫). HTTP 상태 코드는 사용자에게 보이는 말("환율 없음" 오류)로 바꿨다.
- **헌법 명세 작성 규약**: 조용히 깨지는 요구사항마다 실패 양상을 두었고, "일어나지 않음·다른
  곳에서 일어남·늦게 일어남"을 함께 따졌다(FR-001, FR-003, FR-005, FR-013, FR-017, FR-027 등).
