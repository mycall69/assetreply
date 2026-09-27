# Implementation Plan: 일자별 환율 표의 스크롤 탐색과 기간 단위 전환

**Branch**: `004-fx-table-scroll-periods` | **Date**: 2026-09-27
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/004-fx-table-scroll-periods/spec.md`

## Summary

003이 실제 데이터를 채우면서 한 통화에 **17,514행**이 쌓였다. 002가 만든 표는 그 규모를
감당하지 못한다 — 이전 데이터를 보려면 `더 보기`를 수십 번 눌러야 하고, 일 단위로만 볼 수
있어 장기 추이가 안 보인다.

스크롤로 이어 보게 하고, 일·주·월 단위를 고를 수 있게 한다. 주는 금요일, 월은 말일이
기준일이며, 그날 고시가 없으면 **그 구간의 마지막 고시일**을 쓴다.

기술적 무게 중심은 **기준일 선정과 페이지 경계**에 있다. 집계를 서버에서 하고 001의 커서
방식을 그대로 이어, 003의 백그라운드 수집이 조회 중에 돌아도 같은 행이 두 번 나오지 않게
한다. **새로 만드는 저장 구조가 없다.**

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, SQLAlchemy 2.x async |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ — **윈도 함수**(`ROW_NUMBER() OVER PARTITION BY`) 사용 |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library |
| 타입·린트 | mypy strict, ruff / tsc, eslint |
| 집계 위치 | **서버** (research R4-1) |
| 페이지 방식 | 001의 커서(`before=<날짜>`) 계승 (research R4-3) |
| 신규 테이블 | **없음** |
| 외부 호출 | **없음** — 이미 수집된 데이터만 다르게 질의한다 |

NEEDS CLARIFICATION 없음. 명세가 설계로 미룬 항목은 research에서 전부 결정했다.

## Constitution Check

헌법 v5.2.0의 9개 원칙과 제약 섹션에 대한 게이트.

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 기존 비동기 조회 경로를 확장한다. 동기 I/O·`time.sleep` 없음 |
| II. 데이터 소스 격리 | ✅ | 외부 호출이 없다. ECOS 어댑터를 건드리지 않는다 |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행. 기준일 선정·페이지 경계·전환 잔존을 스텁 없이 DB로 검증한다 |
| IV. 모듈화 | ✅ | 기준일 선정은 리포지토리, 표시 판정은 서비스, 강조 매핑은 화면. 계층이 갈린다 |
| V. 데이터 정합성·재현성 | ✅ | **결측을 보간하지 않는다.** 기준일 결측은 값이 아니라 **날짜를 옮겨** 푼다. 집계 결과를 저장하지 않아 재현성 대상이 아니다 |
| VI. 금융 계산 정확성 | ✅ | 파생 환율은 002의 `Decimal` 경로를 그대로 쓴다. 평균·집계 산출이 없다(FR-009) |
| VII. 반응형 UI | ✅ | 상태는 Zustand. 스크롤이 UI를 막지 않는다 |
| VIII. 한국어 문서화 | ✅ | 모든 산출물·주석·커밋이 한국어 |
| IX. MVP/YAGNI | ✅ | 가상 스크롤·집계 테이블·뷰를 도입하지 않는다(R4-1, R4-6) |
| DB 운영 규약 | ✅ | 윈도 함수는 표준 SQL이다. 스키마 변경이 없어 마이그레이션도 없다 |
| 명세 작성 규약 | ✅ | FR 신설 시 plan 추적성·tasks 참조를 같은 작업 단위에서 갱신한다 |

**위반 0건.** Complexity Tracking 불필요.

### 설계 후 재평가

| 원칙 | 판정 | 비고 |
|------|------|------|
| V. 데이터 정합성 | ✅ | R4-2의 "구간의 마지막 고시일" 방식이 보간 경로를 **구조적으로 없앤다**. 값을 채우는 코드가 존재할 자리가 없다 |
| IX. MVP/YAGNI | ⚠️→✅ | 응답에 `periodFrom`·`periodTo`를 더하는 것이 과한지 검토했다. FR-019가 "선택 날짜가 속한 구간"을 요구하므로 기준일만으로는 판정할 수 없다. 유지 |

## Project Structure

### Documentation (this feature)

```
specs/004-fx-table-scroll-periods/
├── spec.md
├── plan.md               # 이 문서
├── research.md           # R4-1 ~ R4-8
├── data-model.md
├── quickstart.md         # 검증 시나리오 21개
├── contracts/
│   ├── rest-api.md
│   └── ui-wireframes.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```
backend/src/
├── repository/fx_rate.py          # [변경] 주·월 기준일 페이지 조회 추가
├── api/services/
│   ├── period_rows.py             # [신규] 기준일 판정·구간 범위·진행 중 판정
│   └── daily_query.py             # [변경] period 매개변수 전달
└── api/routes/daily.py            # [변경] period 질의 매개변수, 응답 필드 4종

frontend/src/
├── components/fx/
│   ├── PeriodTabs.tsx             # [신규] 기간 단위 선택기 (002 CurrencyTabs 형태)
│   ├── DailyTable.tsx             # [변경] 더 보기 제거, 이어 보기, 표시 3종
│   └── PeriodRowBadges.tsx        # [신규] 옮겨진 기준일·진행 중 표시
├── hooks/useInfiniteScroll.ts     # [신규] 스크롤 끝 감지
├── stores/fxWorkspaceStore.ts     # [변경] period 상태, 전환 잔존 방지, 구간 강조
├── lib/types.ts                   # [변경] PeriodUnit·PeriodRow 타입
├── lib/csv.ts                     # [변경] 기간 단위·원래 기준일·진행 중·범위 머리말
└── app/fx/page.tsx                # [변경] PeriodTabs 배치, 내려받기 행 수
```

**구조 선택**: 웹 애플리케이션. 001~003이 세운 배치를 잇는다.

`period_rows.py`를 따로 두는 이유는 기준일 판정이 **조회와 표현 사이**에 있기 때문이다.
리포지토리는 "어느 행을 뽑나"를, 이 모듈은 "그 행이 무엇을 뜻하나"를 책임진다.

## 요구사항 추적성

| 요구사항 | 설계 근거 |
|----------|-----------|
| FR-001·003 (이어 보기·위치 유지) | research R4-3·R4-6, `useInfiniteScroll`, ui-wireframes W3 |
| FR-001a·SC-001b (짧은 표) | research R4-6, `useInfiniteScroll` 가시성 기반, quickstart 1a |
| FR-002·004 (끝 알림·실패 처리) | ui-wireframes W3, quickstart 3·4 |
| FR-005 (중복 방지) | research R4-3 (커서 방식), quickstart 3 |
| FR-005a·005b (표 재수신·위치 초기화) | ui-wireframes W6, quickstart 14 |
| FR-006·007 (단위 선택·기본값) | contracts/rest-api `period` 기본값, ui-wireframes W1 |
| FR-008·009 (기준일·집계 금지) | research R4-2, data-model 4절 |
| FR-010·011 (전환 잔존 금지) | research R4-8, ui-wireframes W5 |
| FR-012 (날짜를 옮긴다) | research R4-2, data-model 4절, 헌법 원칙 V |
| FR-013·014 (옮김 표시) | contracts/rest-api `shiftedFrom` 키 생략, ui-wireframes W2 |
| FR-015 (빈 구간) | data-model 4절 — 질의가 돌려주지 않아 자연히 성립 |
| FR-015a (진행 중) | data-model 5절, ui-wireframes W2 |
| FR-015b (표시 구별) | research R4-4, contracts/rest-api 세 필드 분리 |
| FR-016 (열·서식 계승) | 002 `DailyTable` 재사용 |
| FR-016a·016b·016c (내려받기) | research R4-5, contracts/rest-api 내려받기 절, ui-wireframes W7 |
| FR-017·018 (파생·잠정) | 002 경로 그대로, quickstart 17 |
| FR-019·019a·019b (구간 강조) | research R4-7, ui-wireframes W4 |
| FR-020 (빈 구간 강조 없음) | ui-wireframes W4, quickstart 13 |
| SC-001 (월 단위 도달) | data-model 7절 (749행·25회), quickstart 18 |
| SC-001a (일 단위 끊김 없음) | quickstart 1 |
| SC-002 (위치 유지) | research R4-6, quickstart 2 |
| SC-003·004 (끝·중복) | quickstart 3 |
| SC-005 (기본 일 단위) | quickstart 5 |
| SC-006 (실제 날짜만) | research R4-2 — 존재하는 행만 뽑는다 |
| SC-007·008 (옮김 표시 정확) | quickstart 7·8 |
| SC-009 (빈 구간 행 없음) | data-model 4절 |
| SC-010 (전환 잔존 0) | quickstart 6 |
| SC-011 (행 수 1/20) | data-model 7절 (1/23 실측), quickstart 19 |
| SC-012 (파생·잠정 일관) | quickstart 17 |
| SC-013·014 (선택 날짜 유지·관계 표시) | ui-wireframes W4, quickstart 11·12 |
| SC-015·016 (진행 중·표시 구별) | quickstart 9·10 |
| SC-017 (재수신 분량) | ui-wireframes W6, quickstart 14 |
| SC-018·019 (파일 단위·표시) | quickstart 15·16 |
| SC-020 (범위 표시) | contracts/rest-api 내려받기 표, ui-wireframes W7, quickstart 15 |

## 위험과 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| 주말에 고시가 생기면 기준일 판정이 틀린다 | 옮겨지지 않았는데 옮겼다고 표시 | 한국 외환시장은 주말 고시를 하지 않는다. 명세 Assumptions에 전제를 남겼다 (R4-2) |
| 수집이 조회 중에 행을 추가한다 | 같은 행이 두 번 나옴 | 커서 방식이라 영향 없다. 오프셋이었다면 깨졌다 (R4-3) |
| 표시가 셋으로 늘어 화면이 복잡해진다 | 사용자가 읽지 않음 | 셋이 동시에 참인 경우는 이번 주·이번 달 한 행뿐이다. 나머지는 대부분 표시가 없다 |
| 일 단위 스크롤이 끝없이 느껴진다 | 사용자가 포기 | 의도된 것이다. 장기 구간은 단위를 넓히는 것이 정상 경로다 (SC-001a) |

## Phase 0 산출물

[research.md](./research.md) — 결정 8건 (R4-1 ~ R4-8)

## Phase 1 산출물

- [data-model.md](./data-model.md) — 스키마 변경 없음, 파생 값 정의
- [contracts/rest-api.md](./contracts/rest-api.md) — 기존 엔드포인트 확장
- [contracts/ui-wireframes.md](./contracts/ui-wireframes.md) — W1 ~ W7
- [quickstart.md](./quickstart.md) — 검증 시나리오 21개

## 다음 단계

`/speckit-tasks`로 의존성 순서가 매겨진 태스크를 생성한다.
