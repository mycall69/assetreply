# Implementation Plan: 외환 수집 실행 계층과 실시간 관측 화면

**Branch**: `003-fx-collection-runtime` | **Date**: 2026-09-24
**Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/003-fx-collection-runtime/spec.md`

## Summary

001·002가 수집 엔진·재개 로직·점유 제어·진행률 프로토콜·수집 현황 화면을 모두 만들었으나
**그것을 실행하는 주체가 없다.** `POST /api/fx/collect`는 작업 행을 만들고 점유만 잡은 뒤
202를 돌려주며, `run_collection()`을 호출하는 프로덕션 코드가 한 줄도 없다.

이번 기능은 그 구멍을 메우고, 실행이 생기면서 비로소 의미를 갖는 관측을 붙인다 — 시간축
커버리지 시각화, 수집 기록 적재, 호출 한도 가시화.

화면은 **통화를 하나 골라 그 통화만** 보여주며, 수집도 한 번에 한 통화만 돈다
(2026-09-24 반복).

기술적 무게 중심은 **실행 수명 관리**에 있다. 화면과 무관하게 돌고, 죽어도 점유를 되찾고,
멈춘 것과 도는 것이 구별되어야 한다. 새로 만드는 저장 구조는 수집 이벤트 테이블 하나뿐이며,
나머지는 001·002가 가진 데이터를 다르게 읽는다.

## Technical Context

| 항목 | 값 |
|------|-----|
| 언어 (백엔드) | Python 3.14.x |
| 프레임워크 | FastAPI, aiohttp, SQLAlchemy 2.x async |
| 언어 (프론트엔드) | TypeScript 5.x (`strict`), Next.js 16 App Router, React 19 |
| 상태 관리 | Zustand (헌법 원칙 VII) |
| DB | MySQL 8.0+ (InnoDB, utf8mb4), Alembic |
| 테스트 | pytest·pytest-asyncio / Vitest·React Testing Library |
| 타입·린트 | mypy strict, ruff / tsc, eslint |
| 실행 방식 | **애플리케이션 프로세스 내 비동기 태스크** (research R3-1) |
| 외부 의존 | 한국은행 ECOS. 일일 한도 실측 하한 150회, 전체 백필 약 146회 |
| 신규 테이블 | `fx_collection_event` 1개 |
| 배포 전제 | **단일 워커 프로세스** (`--workers 1`) |
| 수집 동시성 | **한 번에 한 통화** (2026-09-24 반복으로 병행 수집 제거) |

NEEDS CLARIFICATION 없음. 명세가 설계로 미룬 항목은 research에서 전부 결정했다.

## Constitution Check

헌법 v5.1.0의 9개 원칙과 제약 섹션에 대한 게이트.

| 원칙 | 판정 | 근거 |
|------|------|------|
| I. 비동기 우선 | ✅ | 워커가 기존 이벤트 루프의 태스크다. 동기 I/O·`time.sleep` 없음. 대기는 `asyncio.sleep` |
| II. 데이터 소스 격리 | ✅ | ECOS 어댑터를 그대로 쓴다. 신규 외부 호출 없음. 인증 키는 이벤트에 담지 않는다(FR-020) |
| III. TDD (NON-NEGOTIABLE) | ✅ | 테스트 선행. 실행 수명·회수·한도 전파는 스텁 소스로 검증하며 네트워크 없이 통과 |
| IV. 모듈화 | ✅ | 워커(수명)·이벤트(기록)·조회(표현)를 분리한다. 수집 로직은 기존 `ingestion`에 둔 채 건드리지 않는다 |
| V. 데이터 정합성·재현성 | ✅ | 시계열을 쓰지 않는다. 이벤트는 관측 기록이라 재현성 대상이 아니다. 잠정/확정 구분에 영향 없음 |
| VI. 금융 계산 정확성 | ✅ | 금액 계산이 없다. 이벤트의 `rows_stored`는 건수(정수) |
| VII. 반응형 UI | ✅ | 수집 스트림으로 갱신. 상태는 Zustand. 긴 작업이 UI를 막지 않는다 |
| VIII. 한국어 문서화 | ✅ | 모든 산출물·주석·커밋이 한국어 |
| IX. MVP/YAGNI | ✅ | 외부 큐·별도 프로세스를 도입하지 않는다(R3-1). 예약 수집은 범위 밖 |
| DB 운영 규약 | ✅ | Alembic 리비전으로만 변경. 방언 문법은 `db/dialect.py` 뒤에 격리 |
| 명세 작성 규약 | ✅ | FR 신설 시 plan 추적성·tasks 참조를 같은 작업 단위에서 갱신한다 |

**위반 0건.** Complexity Tracking 불필요.

### 설계 후 재평가

| 원칙 | 판정 | 비고 |
|------|------|------|
| IV. 모듈화 | ✅ | 이벤트 기록이 수집 로직에 침투하지 않도록, 수집은 이벤트를 **발행**만 하고 싱크를 모른다 |
| IX. MVP/YAGNI | ⚠️→✅ | `state` 3값(`running`/`stalled`/`awaiting_reclaim`)이 과한지 검토했다. FR-006a가 "회수를 기다리는 중"을 요구하므로 2값으로는 표현할 수 없다. 유지 |
| IX. MVP/YAGNI (2026-09-24 반복) | ✅ | 단일 통화로 좁히면서 `worker/limit.py`의 공유 중단 신호를 제거했다. 존재하지 않는 동시성을 다루는 코드가 사라졌다 (research R3-8) |

## Project Structure

### Documentation (this feature)

```
specs/003-fx-collection-runtime/
├── spec.md
├── plan.md               # 이 문서
├── research.md           # R3-1 ~ R3-10
├── data-model.md
├── quickstart.md         # 검증 시나리오 17개
├── contracts/
│   ├── rest-api.md
│   └── ui-wireframes.md
└── checklists/
    └── requirements.md
```

### Source Code (repository root)

```
backend/src/
├── worker/                       # [신규] 실행 수명
│   ├── runner.py                 #   lifespan이 띄우는 수집 태스크
│   ├── queue.py                  #   시작 요청 전달
│   └── reconcile.py              #   기동 시·주기 미해결 작업 정리 (R3-2)
│                                 #   ※ limit.py는 2026-09-24 반복에서 삭제 (R3-8)
├── observability/                # [신규] 기록
│   ├── events.py                 #   이벤트 값 정의와 발행 지점
│   ├── sinks.py                  #   DB 적재·파일 로깅 두 싱크 (R3-4)
│   └── logging_config.py         #   구조화 포매터, 수집 전용 파일 (R3-10)
├── repository/
│   ├── collection_event.py       # [신규] 적재·조회·보관 정리
│   └── raw_response.py           # [변경] 오늘 호출 수 집계 (R3-5)
├── api/
│   ├── routes/collection.py      # [신규] timeline · stream · events
│   ├── routes/collect.py         # [변경] 202 후 워커에 시작을 넘긴다
│   └── services/timeline.py      # [신규] 통화별 시간축 조합 (R3-6)
├── ingestion/orchestrator.py     # [변경] 이벤트 발행, 중단 신호 확인
├── db/models.py                  # [변경] FxCollectionEvent, events_dropped
└── config/settings.py            # [변경] 멈춤 임계 60초, 보관 20작업

backend/migrations/versions/
└── <rev>_수집_이벤트_테이블.py    # [신규]

frontend/src/
├── app/fx/collection/page.tsx           # [변경] 시간축 중심으로 재구성
├── components/fx/CurrencyTabs.tsx       # [재사용] 002의 것을 옮기지 않고 그대로 (R3-11)
├── components/collection/               # [신규]
│   ├── CurrencyTimeline.tsx             #   시간축 막대 (W2)
│   ├── CurrencyCard.tsx                 #   상태 배지·설명 (W3)
│   ├── RateLimitBanner.tsx              #   전체 배너 (W4)
│   ├── EventList.tsx                    #   최근 기록 (W6)
│   └── IncompleteRecordNotice.tsx       #   기록 불완전 (W5)
├── components/shell/CollectionIndicator.tsx  # [변경] 상시 노출·멈춤·한도 반영 (W7, R3-12)
├── stores/collectionStore.ts            # [변경] 수집 스트림 구독으로 전환
└── lib/collectionStream.ts              # [신규] 수집 스트림 클라이언트
```

**구조 선택**: 웹 애플리케이션(백엔드 + 프론트엔드). 001·002가 세운 배치를 잇는다.

`worker/`와 `observability/`를 나눈 이유는 관심사가 다르기 때문이다. 워커는 **언제 무엇을
돌릴지**를, 관측은 **무슨 일이 있었는지 어떻게 남길지**를 책임진다. 한 모듈에 넣으면 수집
수명 로직과 기록 포맷이 엉킨다.

## 요구사항 추적성

| 요구사항 | 설계 근거 |
|----------|-----------|
| FR-001·002 (백그라운드 실행, 명시적 시작) | research R3-1, `worker/runner.py`, contracts/rest-api `POST /collect` |
| FR-003·004 (통화별 단일, 한 번에 한 통화) | 001의 DB 점유 재사용, contracts/rest-api 409 |
| FR-027 (통화 선택) | research R3-11, 002 `CurrencyTabs` 재사용, ui-wireframes W1 |
| FR-028 (전환 시 잔존 금지) | research R3-11, contracts/rest-api `stream` 통화 대조, ui-wireframes 갱신 범위 |
| FR-029 (진행 중 시작 거절) | contracts/rest-api `busyWith`·409, ui-wireframes W1 |
| FR-030 (진입점 보장) | research R3-12, ui-wireframes W7, tasks T073·T090 |
| FR-005·005a·005b·005c (회수·부분 완료·새 작업·기동 시 즉시) | research R3-2, `worker/reconcile.py`, data-model 상태 전이 |
| FR-006·006a (60초 멈춤·회수 대기) | research R3-3, contracts/rest-api `state` 3값, ui-wireframes W3 |
| FR-007 (정상 종료) | `worker/runner.py` 취소 처리, data-model 상태 전이 |
| FR-008·009 (이어받기·이미 완료) | 001 `next_start_date` 재사용, quickstart 6 |
| FR-010 (재진입 즉시 따라잡기) | contracts/rest-api `snapshot`이 REST와 동일 구조, quickstart 4 |
| FR-011 (이어받기 지점) | research R3-6 (`job.range_start`), ui-wireframes W2 `▲` |
| FR-012·013·014·016 (시간축) | contracts/rest-api `timeline`, ui-wireframes W2·W3 |
| FR-015 (10초 이내 갱신) | contracts/rest-api 5초 하트비트 |
| FR-017·018 (두 경로 적재) | research R3-4, `observability/sinks.py` |
| FR-017a (도달 확인) | `observability/sinks.py` 경로 생존 확인, tasks T091 |
| FR-018a·018b (기록 실패 처리) | research R3-4, data-model `events_dropped`, ui-wireframes W5 |
| FR-019·019a·019b·019c (기록 내용·결과 삼분·건수 구별·시각 기준) | data-model `kind` 표, `observability/events.py` |
| FR-020 (비밀값 차단) | research R3-10 (발행 지점에서 차단), quickstart 15 |
| FR-021 (결측·실패 구별) | data-model `chunk_empty` vs `chunk_failed`, ui-wireframes W6 |
| FR-022 (실시간·사후 조회) | contracts/rest-api `stream`·`events` |
| FR-023·023a (보관 범위) | research R3-9, data-model 보관 규칙, ui-wireframes W6 하단 |
| FR-024 (호출 수) | research R3-5, contracts/rest-api `callsToday` |
| FR-025·025a·026 (한도 표시) | ui-wireframes W4, data-model 상태 전이 |
| SC-001·002 (화면 무관 진행) | quickstart 2·3 |
| SC-003 (중복 호출 0) | quickstart 6 |
| SC-004·005 (갱신·재진입 성능) | contracts/rest-api 하트비트, quickstart 4 |
| SC-006 (이어받기 식별) | ui-wireframes W2, quickstart 5 |
| SC-007·007a·007b (기록 일치·실패) | quickstart 11·13 |
| SC-008 (실패·건너뛴 구간 기록 누락 0) | data-model `chunk_empty`·`chunk_failed`, quickstart 12·13 |
| SC-009 (비밀값) | quickstart 15 |
| SC-010·014 (회수) | quickstart 7 |
| SC-011 (멈춤 구별) | quickstart 8 |
| SC-012·013a (한도 사유) | quickstart 9 |
| SC-016 (전환 시 잔존 0) | quickstart 10 |
| SC-017 (거절 사유 제시) | quickstart 17 |
| SC-018 (대기 상태 도달) | quickstart 18 |
| SC-015 (보관 상한) | quickstart 14 |

## 위험과 대응

| 위험 | 영향 | 대응 |
|------|------|------|
| 다중 워커 프로세스로 띄우면 수집이 중복된다 | 한도 낭비 | DB 점유가 중복 실행은 막는다. `--workers 1`을 배포 전제로 문서화 (R3-1) |
| 개발 중 `--reload`가 워커를 자주 죽인다 | 수집 중단 | FR-005 경로가 상시 검증된다. 단점이 아니라 기회 (R3-1) |
| 이벤트 적재가 수집 성능을 잠식한다 | 수집 지연 | 청크당 사건이 2~3개다. 청크 자체가 외부 호출이라 상대적으로 무시 가능 |
| 전체 백필에 사용자 조작이 3번 필요하다 | 번거로움 | 단일 통화 수집의 의도된 대가다. 한도 소진이 느려지는 이득과 맞바꿨다 (2026-09-24 반복) |
| 001의 `run_all_currencies`가 남아 있다 | 우회 실행 | 003 화면이 그 경로를 쓰지 않는다. 코드는 001 자산이라 지우지 않는다 |
| 한도 집계와 실제 리셋 시각이 어긋난다 | 잘못된 안심 | 참고 지표임을 화면이 명시. 판정은 출처 신호로만 (R3-5) |

## Phase 0 산출물

[research.md](./research.md) — 결정 10건 (R3-1 ~ R3-10)

## Phase 1 산출물

- [data-model.md](./data-model.md) — 신규 테이블 1개, 변경 1개
- [contracts/rest-api.md](./contracts/rest-api.md) — 신규 3개, 동작 변경 1개
- [contracts/ui-wireframes.md](./contracts/ui-wireframes.md) — W1 ~ W7
- [quickstart.md](./quickstart.md) — 검증 시나리오 17개

## 다음 단계

`/speckit-tasks`로 의존성 순서가 매겨진 태스크를 생성한다.
