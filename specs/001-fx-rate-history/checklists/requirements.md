# Specification Quality Checklist: FX 환율 축적·조회·시각화

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-08-30
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

- **[NEEDS CLARIFICATION] 전건 해소** (2026-08-30, `/speckit-clarify` 세션).
  - FR-018 → 고시 없는 날은 "고시 없음"을 주 결과로, 직전 영업일 값은 구분된 참고 정보로 제시
  - FR-026 → 현재 스프레드를 모든 과거 날짜에 적용하고 적용값을 결과에 기록
  - FR-035 → 필요한 구간이 임계값(기본 30일) 이하면 대기, 초과하면 진행 상태 우선 제시
  같은 세션에서 스캔으로 발견한 갭 2건(동시 수집 작업 충돌, 수집 실패 이력 보존)도 함께 해소했다.

- **용어 정규화**: "확보"와 "수집"을 혼용하던 것을 헌법의 계층명 `수집(ingestion)`에 맞춰
  "수집"으로 통일했다.

- **2차 `/speckit-clarify` 세션** (2026-08-30) — 1차에서 누락된 갭 4건을 추가로 해소했다.
  - FR-003a/b: 출처의 정정 발표 시 최신 값으로 갱신하고 원본 응답으로 갱신 전 값 추적
  - FR-032a/b: 차트 요청도 날짜 조회와 동일한 자동 수집 규칙 적용
  - FR-004a/b: 응답 원본을 기한 없이 영구 보관
  - FR-038a/b: 실패 이력 영구 보관, 성공 이력은 설정 기간(기본 90일)만 보관
  이 과정에서 SC-003("반복 조회 시 항상 동일한 값")이 정정 처리 결정과 모순되어 함께 수정했다.

- **구현 세부사항 분리**: 사용자 입력에 포함된 ECOS API의 엔드포인트 형식, 응답 필드명,
  오류 코드 체계는 "No implementation details" 기준에 걸리므로 spec.md에서 제외하고
  `research-inputs/ecos-api-notes.md`로 옮겼다. 검증된 지식이므로 폐기하지 않고
  `/speckit-plan`의 research 입력으로 사용한다.

- **명확화 후보 12건 중 9건은 Assumptions로 해소**: 사용자 입력이 12개 항목을 명확화 대상으로
  제시했으나, 이 커맨드는 최대 3건까지만 마커로 유지한다. 나머지 9건은 합리적 기본값을 선택해
  Assumptions 절에 근거와 함께 기록했다. 기본값이 마음에 들지 않으면 `/speckit-clarify`
  또는 spec 직접 수정으로 뒤집을 수 있다.
