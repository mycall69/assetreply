# Specification Quality Checklist: 외환 수집 실행 계층과 실시간 관측 화면

**Purpose**: 계획 단계로 넘어가기 전 명세의 완결성과 품질을 검증한다
**Created**: 2026-09-24
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

- 배경 설명(Input)에 기존 코드 심볼이 등장하지만, 이는 "무엇을 다시 만들지 않을지"를
  규정하는 범위 경계이며 요구사항 본문에는 구현 수단이 들어가 있지 않다.
- 헌법 v5.1.0 명세 작성 규약에 따라, 조용히 깨질 수 있는 요구사항에는 실패 양상을 함께
  적었다. FR-005a·FR-006a·FR-018a·FR-018b·FR-021·FR-023·FR-025a·FR-028·FR-029가 해당한다.
- 2026-09-24 clarify 세션에서 5개 항목이 확정되며 다음이 해소됐다.
  - FR-006의 "일정 시간"이 60초로 정량화됐다.
  - FR-023의 보관 범위가 통화별 최근 20개 작업으로 정해졌다. 설계 단계로 미루지 않았다.
  - **FR-004와 FR-025 사이의 모순이 해소됐다.** 호출 한도는 인증 키 단위 공유 자원이라
    통화 간 격리 원칙의 예외임을 FR-004a로 명시했다. (※ 2026-09-24 반복에서 단일 통화로
    좁히면서 이 모순 자체가 소멸해 FR-004a를 삭제했다.)
  - **FR-018이 만족 불가능했던 문제가 해소됐다.** 한쪽 기록만 실패하면 어느 구현도 위반일
    수밖에 없었다. 정상 동작으로 한정하고 FR-018a·018b로 실패 경로를 규정했다.
- 비정상 종료 후 작업 상태(부분 완료)와 재시작 시 새 작업 생성 규칙이 FR-005a·005b로
  들어오면서, 작업 단위의 의미가 "한 번의 실행 시도"로 확정됐다.
- **2026-09-24 반복(단일 통화 표시)으로 범위가 줄었다.**
  - 삭제: FR-004a(한도 전체 중단), SC-013(통화 격리). FR-004는 "한 번에 한 통화"로 재정의
  - 신설: FR-027(선택), FR-028(전환 시 잔존 금지), FR-029(진행 중 거절), SC-016, SC-017
  - 원 요청은 화면 표시에 관한 것이었으나 사용자가 수집 동작까지 단일 통화로 좁히기를
    택했다. 요구사항 삭제를 동반하므로 여기 남긴다.
  - FR-028은 002의 FR-036c와 같은 계열의 결함을 겨냥한다 — 통화를 바꿨는데 이전 통화의
    결과가 화면에 남는 문제다. 그때는 구현 후에 발견했고, 이번에는 요구사항 단계에서
    실패 양상과 함께 적었다.
- **2026-09-24 2차 반복(수집 현황 진입점)으로 결함 하나를 메웠다.**
  - 신설: FR-030(진입점 보장), SC-018
  - 사이드바에 수집 현황이 없고 유일한 링크인 표시기가 진행 중일 때만 나타나, 한 번도
    수집하지 않은 상태에서는 시작할 방법이 없었다. **US1~US4 전부가 도달 불가능했다.**
  - **와이어프레임이 화면 배치는 그렸으나 "사용자가 이 화면에 어떻게 도착하는가"를 묻지
    않아 생긴 누락이다.** 요구사항 품질 관점에서, 화면을 정의하는 명세에는 그 화면으로
    가는 경로도 함께 규정되어야 한다는 교훈이 남는다.
  - 사용자가 실제 화면 스크린샷을 보고 물어서 드러났다. 문서만 대조하는 검증으로는
    잡히지 않는 종류였다.
