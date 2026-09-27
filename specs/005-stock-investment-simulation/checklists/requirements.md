# Specification Quality Checklist: 주식 투자 시뮬레이션

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-27
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

- **16/16 통과** (2026-09-27 specify 3건 + clarify 5건 반영, 총 8건).
- clarify 5건: 시세 수집 범위(요청 구간만·커버리지 재개), 매매 수수료 계산(수수료 포함
  총액 기준 수량), 시세 단절 처리(마지막 시세일까지·사실을 알림), 수집 중 사용자 경험
  (001~003 방식 계승), 종목 지정(검색 후 선택).
- clarify 후 검증에서 **새 요구사항이 어느 인수 기준에도 걸려 있지 않은 것**을 발견해
  US1에 시나리오 5건을 더했다 — 검색, 수집 진행, 중복 수집 차단, 재실행 시 재수집 없음,
  시세 단절.
- 반영된 결정: FR-010a·010b(제공처 이벤트를 그대로 적용하되 적용 내역을 남긴다),
  FR-037·037a·037b(브라우저 보관, 그 사실을 알림, 사용자가 지울 수 있음),
  FR-041·041a·041b·041c(원금 통화 기준, 기준일마다 환산, 평가에는 매매기준율).
- 수익률 기준 통화를 원금 통화로 정한 것이 파급이 가장 컸다. 초기 환전 한 번으로
  끝나던 환율 의존이 **기준일마다의 환산**으로 늘었고, 환율 결측 처리(FR-041c)와
  환율 종류 구분(FR-041b)이 함께 생겼다.
- **헌법 원칙 IX 결정이 별도로 남아 있다.** 주식은 자산군 순서상 세 번째인데 가상자산이
  아직 없다. 체크리스트 항목은 아니지만 `/speckit-plan`의 Constitution Check가 막는다.
- Items marked incomplete require spec updates before `/speckit-clarify` or `/speckit-plan`
