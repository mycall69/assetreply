# Implementation Plan: 외환 분석 화면 통합과 전역 내비게이션 셸

**Branch**: `002-fx-analysis-workspace` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-fx-analysis-workspace/spec.md`

## Summary

001의 4개 탭을 하나의 외환 분석 화면으로 합치고, 자산군 전역 내비게이션 셸을 도입한다.
스프레드 설정은 설정 화면으로 옮기고 기본값 복원을 붙인다. 오늘 환율을 잠정값으로 다루는
경로를 새로 만든다.

기술적으로 이번 기능의 무게 중심은 UI가 아니라 **잠정값 취급**에 있다. 헌법 v5.0.0 원칙 V가
확정/잠정 구분을 MUST로 규정했으므로, `fx_rate`에 상태를 더하고 커버리지·재개·upsert가 그
상태와 어긋나지 않도록 맞추는 것이 설계의 핵심이다. 특히 잠정 레코드가 "수집 완료"로 오인되면
확정값이 영원히 들어오지 않는다(research R2-2·R2-3).

두 번째 축은 **파생 환율의 산출 위치**다. 표가 30행 × 4종 파생을 요구하는데, 브라우저에는
`Decimal`이 없다. 클라이언트에서 계산하면 원칙 VI가 API 경계에서 무력화되므로 서버가 산출해
문자열로 내려준다(research R2-5).

## Technical Context

**Language/Version**: Python 3.14.x (백엔드), TypeScript 5.0+ (프론트엔드) — 001과 동일

**Primary Dependencies**: 신규 의존성 없음. 001의 FastAPI / aiohttp / SQLAlchemy 2.x async /
Alembic / Next.js 16+ / React 19+ / Zustand / Lightweight Charts / Tailwind CSS를 그대로 쓴다.
전역 셸은 App Router의 중첩 레이아웃으로, CSV 생성은 브라우저에서 처리한다(research R2-7).

**Storage**: MySQL 8.0+ (InnoDB, utf8mb4). 스키마 변경 2건 — `fx_rate`에 확정/잠정 상태 컬럼,
`fx_collection_lock`에 잠금 범위 컬럼. 모두 Alembic 리비전으로 관리 (research R2-1, R2-10)

**Testing**: pytest + pytest-asyncio (백엔드) / Vitest + React Testing Library (프론트엔드).
전체 스위트는 네트워크 없이 통과해야 한다

**Target Platform**: Windows 11 / Linux / macOS. 브라우저는 최신 Chromium·Firefox·Safari

**Project Type**: Web application (backend + frontend 분리) — 001 구조 확장

**Performance Goals**:
- 외환 화면 첫 진입 시 요약·차트·표 모두 3초 이내 (SC-009a)
- 전 구간 차트 조작 1초 이내 (SC-009)
- 스프레드 변경 후 재산출 2초 이내 (SC-005)
- 오늘 새로고침 1회 = 외부 호출 1회 (SC-008)

**Constraints**:
- 확정/잠정을 구분하지 않은 저장·표시 금지, 잠정의 가변성이 확정 구간으로 전파 금지 (헌법 V)
- 금융 계산에 `float` 금지. 파생 환율은 서버에서 `Decimal`로 산출해 문자열로 전달 (헌법 VI)
- 결측치 임의 보간 금지 — 고시 없는 날은 표에 행을 만들지 않고 차트에서 잇지 않는다 (헌법 V)
- DB 접근은 ORM 경유, 방언 문법은 `db/dialect.py`에만 (헌법 v5.0.0 DB 운영 규약)
- 요청 처리 경로에 동기 블로킹 호출 금지 (헌법 I)
- 커버리지 80% 이상, mypy strict, TypeScript `strict: true` + `any` 금지

**Scale/Scope**:
- 시계열 규모는 001과 동일 (약 38,200행). 이번 기능이 데이터량을 늘리지 않는다
- 잠정 레코드는 통화당 최대 1행(오늘)만 존재한다
- 개인 사용 규모. 다중 사용자 동시 접속 부하는 범위 밖

## Constitution Check

*GATE: Phase 0 이전 통과 필수. Phase 1 설계 후 재확인.*

헌법 v5.0.0의 9개 원칙과 도메인 범위 규범에 대한 게이트.

| # | 원칙 | 게이트 | Phase 0 | Phase 1 |
|---|------|--------|:-------:|:-------:|
| I | 비동기 우선 | 새로고침은 `aiohttp`, DB는 비동기 ORM 세션. 요청 경로에 동기 호출 없음 | PASS | PASS |
| II | 데이터 소스 격리 | 오늘 값 조회도 기존 `EcosClient`를 통한다. ECOS 타입이 `ingestion/ecos/` 밖으로 나가지 않음. 새 설정값은 선언으로 추가 | PASS | PASS |
| III | TDD [필수] | 테스트 선행 커밋, 최초 실패는 예정된 것. 구현 후 실패가 남으면 중단·보고. 커버리지 80%+. 네트워크 없이 전체 통과 | PASS | PASS |
| IV | 모듈화 | 파생 환율 산출은 `simulation/spread_calc.py` 순수 함수 재사용. 셸·화면은 UI 계층. CSV 조립은 표현 계층 | PASS | PASS |
| V | 데이터 정합성·재현성 | `fx_rate.is_provisional`로 확정/잠정 구분 저장. 커버리지는 확정만 반영(R2-2). 잠정→확정은 값 재수신으로만(R2-3). 전환 이력은 원본 응답 기록으로 추적. 보간 금지 유지 | PASS | PASS |
| VI | 금융 계산 정확성 | 파생 환율은 **서버**에서 `Decimal` 산출 후 문자열 전달. 브라우저에서 `number` 변환 금지. CSV도 문자열 원본 사용(R2-5, R2-7) | PASS | PASS |
| VII | 반응형 UI | Zustand 상태 관리. 선택 날짜를 단일 소스로 공유. 차트는 Lightweight Charts + 서버측 LTTB | PASS | PASS |
| VIII | 한국어 문서화 | 주석·docstring·커밋 메시지·설계 문서 한국어. 식별자는 원어 | PASS | PASS |
| IX | MVP 점진 개발 | 자산군은 여전히 FX 하나만 구현한다. 미구현 메뉴는 **정적 레이블 + 비활성**이며 라우트·API·수집 코드를 만들지 않는다(R2-9) | PASS | PASS |
| — | 축적 범위 (도메인 규범) | 통화별 탐색 시작일은 001의 설정값을 그대로 쓴다. 이번 기능이 날짜를 코드에 새로 심지 않는다 | PASS | PASS |

**Phase 0 판정: 통과.** 위반 없음.

**Phase 1 재확인 판정: 통과.** 설계 산출물이 게이트를 유지한다. 세 지점에서 헌법이 설계를
직접 결정했다.

- **원칙 VI가 파생 환율의 산출 위치를 결정** — 표는 30행 × 4종 파생을 요구한다. 브라우저에는
  `Decimal`이 없으므로 클라이언트 계산은 곧 IEEE 754 연산이고, 이는 원칙 VI를 API 경계에서
  무력화한다. 서버 산출 + 문자열 전달로 확정했다(research R2-5).
- **원칙 V가 커버리지 규칙을 결정** — 잠정 레코드를 커버리지에 반영하면 재개 로직이 그 날짜를
  건너뛰어 확정값이 영원히 들어오지 않는다. 커버리지는 확정 수집만 갱신한다(research R2-2).
- **원칙 IX가 잠금 설계를 결정** — 새로고침 전용 잠금 테이블을 새로 만드는 대신 기존
  `fx_collection_lock`에 범위 컬럼을 더해 재사용한다. 새 개념을 늘리지 않으면서 FR-036a의
  "수집과 독립"을 만족한다(research R2-10).

**원칙 IX에 대한 보충 판단.** 미구현 자산군 메뉴를 노출하는 것이 "한 번에 하나씩 완결"에
걸리는지 검토했다. 원칙 IX가 금지하는 것은 "여러 자산군의 수집 계층만 먼저 만들고 UI를
미루는 것"이다. 이번 설계는 다른 자산군의 수집·API·데이터 모델을 **전혀 만들지 않고**, 정적
레이블과 비활성 상태만 둔다. 라우트를 만들지 않으므로 이동할 화면 자체가 없다. 구현 대상이
늘지 않으므로 위반이 아니라고 판단한다.

## Project Structure

### Documentation (this feature)

```text
specs/002-fx-analysis-workspace/
├── spec.md                          # 기능 명세 (완료)
├── plan.md                          # 이 문서
├── research.md                      # Phase 0 산출물
├── data-model.md                    # Phase 1 산출물 — 001 스키마 대비 변경분
├── quickstart.md                    # Phase 1 산출물
├── contracts/                       # Phase 1 산출물
│   ├── rest-api.md                  # 신설·변경 엔드포인트
│   ├── ui-wireframes.md             # 화면별 와이어프레임과 상태 배치
│   └── ui-interaction.md            # 선택 날짜 연동 규칙
├── checklists/
│   └── requirements.md              # 명세 품질 체크리스트 (16/16 통과)
└── tasks.md                         # Phase 2 (/speckit-tasks 산출물)
```

### Source Code (repository root)

001 구조를 유지하고 아래를 추가·변경한다. `[신규]`·`[변경]`으로 표시한다.

```text
backend/
├── src/
│   ├── config/settings.py           # [변경] 표 기본 행 수, 새로고침 잠금 만료
│   ├── ingestion/
│   │   └── today.py                 # [신규] 오늘 하루치 조회 — 잠정 저장 전용 경로
│   ├── repository/
│   │   ├── fx_rate.py               # [변경] 확정/잠정 구분 upsert·조회
│   │   ├── coverage.py              # [변경] 잠정은 커버리지 미반영 (R2-2)
│   │   └── collection_lock.py       # [변경] 잠금 범위(scope) 지원 (R2-8)
│   ├── simulation/spread_calc.py    # [재사용] 파생 환율 순수 함수. 변경 없음
│   ├── api/
│   │   ├── routes/
│   │   │   ├── daily.py             # [신규] 표 전용 — 파생 환율 포함 일자별 목록
│   │   │   ├── latest.py            # [신규] 요약 — 최근 값과 직전 대비 변화
│   │   │   ├── today.py             # [신규] 오늘 새로고침
│   │   │   └── spreads.py           # [변경] 기본값 복원 추가
│   │   └── services/
│   │       ├── daily_query.py       # [신규] 일자별 + 파생 산출 조합
│   │       └── today_refresh.py     # [신규] 잠정 저장, 중복 요청 합류
│   └── db/
│       ├── models.py                # [변경] is_provisional, lock scope
│       └── migrations/versions/     # [신규] 리비전 2건
└── tests/                           # [신규] 계약·통합·단위 테스트

frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx               # [변경] 전역 셸(사이드바 + 상단 바)
│   │   ├── page.tsx                 # [변경] 대시보드 자리 — 준비 중 안내
│   │   ├── fx/page.tsx              # [신규] 외환 분석 화면 (001의 4탭 통합)
│   │   └── settings/page.tsx        # [신규] 설정 — 외화 스프레드
│   ├── components/
│   │   ├── shell/                   # [신규] Sidebar, TopBar, CollectionIndicator
│   │   ├── fx/                      # [신규] CurrencyTabs, RateSummary, TrendChart,
│   │   │                            #        DailyTable, TodayRefresh, PeriodPresets
│   │   └── settings/                # [신규] SpreadForm, RestoreDefaultsDialog
│   ├── stores/fxWorkspaceStore.ts   # [신규] 선택 통화·날짜·기간 단일 상태
│   └── lib/csv.ts                   # [신규] 문자열 값 그대로 조립 (R2-7)
└── tests/                           # [신규]
```

**Structure Decision**: 001의 5계층 경계를 그대로 유지한다. 이번 기능이 새로 만드는 것은
대부분 API 조합 서비스와 UI이며, 계산은 기존 `simulation/`을 재사용한다.

세 경계가 특히 중요하다.

- `simulation/spread_calc.py`는 **변경하지 않는다.** 표의 4종 파생도 001과 같은 함수를 쓴다.
  같은 입력에 다른 결과가 나오면 FR-023과 001의 재현성 보장이 함께 깨진다.
- `ingestion/today.py`는 오늘 값을 가져오되 **커버리지를 갱신하지 않는다.** 이 경계가 무너지면
  research R2-2의 전제가 깨지고 확정 전환이 영원히 일어나지 않는다.
- `lib/csv.ts`는 서버가 준 문자열을 **파싱하지 않고** 조립만 한다. `Number()`가 한 번이라도
  끼면 원칙 VI가 파일 출력 단계에서 무너진다.

## Traceability

| 요구사항 | 다루는 산출물 |
|----------|---------------|
| FR-001~005 (전역 셸) | contracts/ui-wireframes W1, research R2-9 |
| FR-005 (미구현 메뉴) | research R2-9, plan 원칙 IX 보충 판단 |
| FR-006~010 (통화·선택 날짜) | contracts/ui-interaction, `stores/fxWorkspaceStore.ts` |
| FR-011~014 (요약) | contracts/rest-api `GET /api/fx/latest`, ui-wireframes W2 |
| FR-015~019 (차트) | contracts/rest-api `GET /api/fx/series`(기존), research R2-4 |
| FR-017a/b (차트 잠정·끝점 보존) | research R2-4 — LTTB가 첫·끝 점을 항상 보존함을 확인 |
| FR-020~026 (상세 표) | contracts/rest-api `GET /api/fx/daily`, research R2-5 |
| FR-022a (선택 날짜가 표 밖) | contracts/ui-interaction 갱신 범위 표 |
| FR-023 (파생 산출) | research R2-5, `simulation/spread_calc.py` 재사용 |
| FR-027~035 (스프레드 설정·복원) | contracts/rest-api `POST /api/fx/spreads/restore`, ui-wireframes W4 |
| FR-031a (복원 부분 실패) | contracts/rest-api restore 응답의 `restored` 목록 |
| FR-036~036b (새로고침 동시성) | research R2-10, data-model `fx_collection_lock.scope` |
| FR-037~037b (잠정 저장·전환·커버리지) | research R2-1·R2-2·R2-3, data-model `fx_rate.is_provisional` |
| FR-038~041 (갱신 시각·실패·전파) | contracts/rest-api `POST /api/fx/today/refresh` |
| FR-042~043 (재현성·전환 추적) | research R2-3, data-model 상태 전이 |
| FR-044~047 (내려받기) | research R2-7, `lib/csv.ts` |
| FR-010 (범위 판정) | contracts/ui-interaction 조회 가능 범위, research R2-6 |
| FR-048 (자동 수집 규칙) | contracts/rest-api `latest`·`daily`의 202 분기 |
| FR-049 (수집 알림) | contracts/ui-wireframes W1 상단 표시기 |
| SC-005·009·009a (성능) | research R2-6, quickstart 시나리오 8 |
| SC-007·007a (잠정 구분·시점 일치) | quickstart 시나리오 4·5, tasks T037 |
| SC-008 (호출 1회) | research R2-10, quickstart 시나리오 4 |
| SC-003 (확정 재현성) | quickstart 시나리오 6 |

## Complexity Tracking

> Constitution Check에 위반이 없으므로 비워 둔다.

정당화가 필요한 헌법 위반 없음.
