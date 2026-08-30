# Contract: ECOS 어댑터 (내부)

**Feature**: 001-fx-rate-history | **Date**: 2026-08-30

헌법 원칙 II에 따라 ECOS 고유 개념은 `ingestion/ecos/` 밖으로 나가지 않는다.
이 문서는 그 경계의 계약을 정의한다. ECOS 자체 사실은 `../research-inputs/ecos-api-notes.md` 참조.

## 도메인 인터페이스 (`ingestion/protocols.py`)

```text
FxRateSource (Protocol)
  async fetch_daily_rates(currency_code, date_from, date_to) -> FetchResult
  async verify_item_mapping(currency_code) -> ItemMapping
```

**반환 타입은 전부 도메인 타입이다.** `TIME`, `DATA_VALUE`, `RESULT`, `ITEM_CODE` 같은 ECOS 필드명이
이 경계를 넘으면 원칙 II 위반이다.

```text
FetchResult
  quotes: list[DailyQuote]      # 값이 있는 날만. 없는 날은 행 자체가 없다
  outcome: NO_DATA | OK         # NO_DATA는 정상 (구간에 고시가 없었음)
  raw_body: str                 # 원본 보관용 (FR-004a)
  raw_status: int
  raw_result_code: str | None

DailyQuote
  quote_date: date
  base_rate: Decimal            # float 금지 (원칙 VI)
  quote_unit: int               # JPY=100
```

## 오류 분류

출처가 오류를 HTTP 200으로 반환하므로 **본문 판별이 필수**다. 상태 코드만 보면 오류를 성공으로
오인해 빈 데이터를 저장하게 된다.

| 출처 신호 | 도메인 예외 | 재시도 | 처리 |
|-----------|-------------|:------:|------|
| 정상 응답 | — | — | `outcome=OK` |
| `INFO-200` | — | — | `outcome=NO_DATA`. **오류가 아니다** |
| `INFO-100` | `SourceAuthError` | ✗ | 즉시 중단. 인증키 문제는 재시도가 무의미 |
| `INFO-300` | `SourceRateLimited` | ✓ | 지수 백오프 + 지터. 지속되면 작업 중단 (FR-013) |
| `ERROR-*` | `SourceError` | ✓ | 백오프 재시도 |
| 비-JSON 본문 | `SourceUnavailable` | ✓ | 차단·점검 페이지. JSON 파싱 실패와 구분해 기록 |
| 항목 매핑 불일치 | `ItemMappingChanged` | ✗ | 중단. **값을 저장하지 않는다** (FR-015) |

## 항목 매핑 검증 (FR-015)

수집 시작 전 통화별로 1회 수행한다.

1. 항목 목록을 조회한다. 응답 필드는 `ITEM_CODE` / `ITEM_NAME`이다 (`ITEM_CODE1` 아님 — 기존 구현이
   여기서 실패했다).
2. 저장된 `currency.source_item_code`가 목록에 있고 이름이 통화 패턴(미국달러 / 일본엔 / 유로)과
   일치하면 통과.
3. 불일치하면 이름 패턴으로 재탐색해 새 코드를 찾고 `currency.source_item_code`를 갱신한다.
4. 재탐색도 실패하면 `ItemMappingChanged`를 던지고 **해당 통화의 수집을 중단한다**.

## 설정 (코드 아닌 선언 — FR-009, 원칙 II)

| 키 | 기본값 | 근거 |
|----|--------|------|
| `ecos.chunk_days` | 365 | research R2 |
| `ecos.chunk_delay_ms` | 1000 | research R2 |
| `ecos.max_concurrent_per_currency` | 1 | FR-015a |
| `ecos.max_concurrent_currencies` | 3 | FR-015c |
| `ecos.retry_max_attempts` | 5 | |
| `ecos.retry_base_delay_ms` | 1000 | 지수 백오프 기준 |
| `collection.sync_threshold_days` | 30 | FR-035b |
| `job_history.success_retention_days` | 90 | FR-038b |

인증키는 환경변수 `ECOS_API_KEY`. 설정 파일과 저장소에 두지 않는다.

## 계약 테스트 픽스처 (원칙 III)

`backend/tests/contract/fixtures/`에 저장하며, **전체 테스트 스위트는 네트워크 없이 통과해야 한다**.

| 픽스처 | 검증 대상 |
|--------|-----------|
| `search_ok.json` | 정상 파싱, `Decimal` 변환, 쉼표 포함 `DATA_VALUE` 처리 |
| `search_ok_jpy.json` | `quote_unit=100` 보존 |
| `search_mixed_items.json` | 매매기준율 외 항목이 섞인 응답의 필터링 |
| `info_200_no_data.json` | `NO_DATA`가 오류로 처리되지 않음 |
| `info_100_bad_key.json` | `SourceAuthError`, 재시도 안 함 |
| `info_300_rate_limit.json` | `SourceRateLimited`, 백오프 발동 |
| `blocked_page.html` | 비-JSON → `SourceUnavailable`, JSON 파싱 실패와 구분 |
| `item_list_ok.json` | `ITEM_CODE`/`ITEM_NAME` 매핑 검증 통과 |
| `item_list_changed.json` | 코드 변경 시 이름 기반 재탐색 |
| `item_list_unmappable.json` | `ItemMappingChanged`, 저장 없이 중단 |
