# Specification Quality Checklist: 일자별 환율 표의 스크롤 탐색과 기간 단위 전환

**Purpose**: 계획 단계로 넘어가기 전 명세의 완결성과 품질을 검증한다
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

- 배경 설명(Input)과 Dependencies에 001·002·003의 요구사항 번호가 등장하지만, 이는
  **무엇을 계승하고 무엇을 대체하는지**를 규정하는 범위 경계다. 요구사항 본문에는 구현
  수단이 들어가 있지 않다.
- 헌법 v5.2.0 명세 작성 규약에 따라 실패 양상을 함께 적었다. 특히 세 갈래를 의식했다.
  - **일어나지 않음** — FR-002(끝에 도달했는데 알리지 않음), FR-004(조용히 멈춤)
  - **다른 곳에서 일어남** — FR-011(이전 단위 응답이 새 표에 섞임), FR-013(옮겨진 기준일을
    원래 기준일로 오해)
  - **늦게 일어남** — 해당 없음. 이 기능에는 시간 차원의 실패가 없다
- **FR-013이 이 명세의 핵심이다.** 값은 정확한데 무엇의 값인지를 잘못 알게 되는 경우로,
  오류를 내지 않고 조용히 깨진다. 003에서 겪은 결함들과 같은 계열이다.
- FR-010(단위 전환 시 잔존 금지)은 **같은 계열의 결함을 세 번째로 막는다.** 002 FR-036c
  (오늘 환율 새로고침), 003 FR-028(통화 전환)에 이어서다. 앞의 둘은 구현 후에 발견했고
  003부터 요구사항 단계에서 막기 시작했다.
- FR-012의 "값이 아니라 날짜를 옮긴다"는 헌법 원칙 V(결측치 임의 보간 금지)를 지키는
  방식이다. 5-01 자리에 4-30 값을 넣으면 "전일 값 자동 복사" 금지에 걸린다.
- SC-011(행 수 1/20 이하)의 근거: 60년치 월 단위는 약 720행, 일 단위는 약 17,500행이다.
  실측값(USD 17,514행)에서 나왔다.
