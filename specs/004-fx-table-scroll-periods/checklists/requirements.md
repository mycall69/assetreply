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

### 2026-09-27 clarify 세션 (5문항)

5개 항목이 확정되며 다음이 해소됐다. FR 20 → 28, SC 12 → 20.

| 확정 | 내용 |
|------|------|
| 선택 날짜 강조 | **구간 포함 기준.** 선택 날짜는 시점이지 특정 행이 아니다. 단위를 바꿔도 선택 자체는 바뀌지 않는다(FR-019a·019b, SC-013·014) |
| 진행 중인 구간 | 이번 주·이번 달도 **행으로 만들되 진행 중임을 표시**한다. 빼면 주 6일·월 30일치 최신 데이터가 안 보인다(FR-015a) |
| 과거 날짜 선택 | **표를 새로 받는다.** 002 FR-022a를 잇는다. 이어 붙이면 30년치를 한꺼번에 받게 된다(FR-005a·005b) |
| 내려받기 | **화면과 같은 단위.** 옮겨진 기준일·진행 중 표시도 파일에 남긴다 — 빠지면 화면에서 막은 오해가 파일에서 되살아난다(FR-016a·016b) |
| 스크롤 도달 목표 | **단위별로 나눈다.** 월 단위는 전체 도달, 일 단위는 끊김 없음까지만(SC-001·001a) |

**명세 결함 하나를 clarify가 잡았다.** SC-001이 "스크롤만으로 가장 이른 날짜까지 도달"을
모든 단위에 요구했는데, 일 단위는 17,514행이라 30행씩 584번 불러와야 한다. 달성 불가능하고
인수 테스트로도 쓸 수 없는 기준이었다. 단위별로 나눠 측정 가능하게 고쳤다.

**FR-015b가 이번 세션에서 새로 필요해진 요구사항이다.** 한 행에 붙을 수 있는 표시가
셋(옮겨진 기준일·진행 중·잠정값)으로 늘면서, 서로 구별되지 않으면 사용자가 이유를 알 수
없어 표시가 무의미해진다. 요구사항이 늘어난 결과로 생긴 새 위험이다.
