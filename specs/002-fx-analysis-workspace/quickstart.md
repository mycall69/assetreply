# Quickstart: 외환 분석 화면 통합과 전역 내비게이션 셸

**Feature**: 002-fx-analysis-workspace | **Date**: 2026-08-30

이 문서는 기능이 실제로 동작함을 증명하는 **검증 시나리오**다. 구현 코드는 담지 않는다.

## 전제

| 항목 | 값 |
|------|-----|
| Python | 3.14.x (헌법 v5.0.0) |
| 실행 | `./start.sh` (BE 8080 / FE 3030) |
| DB | 001 스키마 + 이번 리비전 2건 적용 |
| 데이터 | USD 최소 1년치 수집 완료 |

```bash
backend/.venv/bin/python -m alembic upgrade head    # 리비전 적용
./start.sh                                          # http://localhost:3030
```

브라우저는 **3030만** 쓴다. `/api/fx/*`는 8080으로 프록시된다(001 research R13).

---

## 1. 전역 셸과 미구현 메뉴 (FR-001~005)

브라우저에서 `http://localhost:3030` 접속.

**기대**
- 왼쪽에 8개 메뉴가 보이고, 외환을 제외한 자산군에 "준비중" 표시가 있다
- "주식"을 클릭해도 아무 일도 일어나지 않는다. 빈 화면이나 오류로 이동하지 않는다
- Tab 키로 이동할 때 "준비중" 항목에 포커스가 가지 않는다
- 외환을 선택하면 좌측 강조 바가 옮겨가고 상단에 "외환"이 표시된다

---

## 2. 한 화면에서 조회 (US1 / FR-006~026)

외환 화면에서 통화 USD 선택.

**기대**
- 요약에 가장 최근 매매기준율이 큰 숫자로, 기준 날짜와 통화쌍이 함께 보인다
- 아래에 차트, 그 아래에 일자별 표가 한 화면에 있다
- 표에 날짜·매매기준율·파생 4종이 나열되고, **주말 날짜의 행이 없다**
- 표 하단에 "현재 스프레드를 각 날짜에 적용한 가정" 안내가 있다

```bash
curl "localhost:8080/api/fx/daily?currency=USD&limit=5" | head -c 600
```

응답의 `rows[].derived`가 문자열이고, 날짜가 연속하지 않는지 확인한다.

---

## 3. 선택 날짜 3영역 연동 (US2 / FR-008, FR-009, SC-002)

**기대** — 아래 세 조작이 모두 같은 결과를 낸다.

1. 날짜 입력에 과거 영업일을 넣는다 → 차트 강조선과 표 강조 행이 그 날짜로 이동
2. 차트의 한 지점을 지정한다 → 날짜 입력과 표 강조 행이 따라옴
3. 표의 한 행을 지정한다 → 날짜 입력과 차트 강조선이 따라옴

**추가 확인**: 선택 날짜를 여러 번 바꾸는 동안 **네트워크 요청이 발생하지 않아야 한다**
(contracts/ui-interaction 갱신 범위 표). 브라우저 개발자 도구 Network 탭에서 확인한다.

**표 범위 밖 선택 (FR-022a)**: 차트에서 표의 30행보다 훨씬 과거인 시점을 지정한다.

**기대**: 표가 그 날짜를 첫 행으로 다시 로드되고 강조된다. 강조할 행이 없는 채로 남지 않는다.
Network 탭에 `daily?...&before=<선택날짜+1일>` 요청이 **한 번만** 나간다.

---

## 4. 오늘 새로고침과 잠정 표시 (US4 / FR-036~041, SC-007, SC-008)

```bash
curl -X POST localhost:8080/api/fx/today/refresh \
  -H 'Content-Type: application/json' -d '{"currency":"USD"}'
```

**기대**
- 평일 고시 후: `status: "updated"`, `isProvisional: true`, `fetchedAt` 포함
- 주말·공휴일: `status: "no_quote_today"` — 값을 만들어내지 않는다
- 화면의 요약에 `⚠ 잠정` 배지와 갱신 시각이 나타난다
- 표 첫 행과 차트 마지막 구간에도 잠정 구분이 보인다(SC-007)

**호출 1회 확인 (SC-008)**: 새로고침 직후 `fx_raw_response`에 한 건만 추가되었는지 본다.

**중복 요청 합류 (FR-036b)**: 같은 요청을 거의 동시에 두 번 보내면 두 번째에
`joinedExisting: true`가 온다.

---

## 5. 수집과 새로고침의 독립 (FR-036a)

USD 대량 수집을 시작한 직후, 수집이 도는 동안 새로고침을 실행한다.

```bash
curl -X POST localhost:8080/api/fx/collect -d '{"currency":"USD"}'
curl -X POST localhost:8080/api/fx/today/refresh -d '{"currency":"USD"}'
```

**기대**: 새로고침이 거부되지 않고 정상 응답한다. 수집도 중단되지 않는다.
`fx_collection_lock`에 `scope`가 다른 두 행이 공존한다.

---

## 6. 잠정값이 확정 구간을 오염시키지 않음 (FR-042, SC-003)

```bash
curl "localhost:8080/api/fx/rates/USD?date=2026-08-15" > before.json
curl -X POST localhost:8080/api/fx/today/refresh -d '{"currency":"USD"}'
curl "localhost:8080/api/fx/rates/USD?date=2026-08-15" > after.json
diff before.json after.json
```

**기대**: 차이 없음. 오늘 값을 몇 번 갱신해도 확정된 과거 값은 변하지 않는다.

---

## 7. 잠정 → 확정 전환 (FR-037a, FR-037b, research R2-2·R2-3)

날짜가 바뀐 뒤(또는 오늘 잠정 행의 `quote_date`를 어제로 조작한 뒤) 증분 수집을 실행한다.

**기대**
- 그 날짜의 행이 실제 값으로 갱신되고 `is_provisional`이 `FALSE`가 된다
- **증분 수집이 그 날짜를 건너뛰지 않는다** — 커버리지가 잠정 때문에 전진해 있으면 이 검증이
  실패한다. R2-2의 규칙이 지켜지는지 확인하는 시나리오다
- `fx_raw_response`에 잠정 시점과 확정 시점의 응답이 모두 남아 값 변화를 대조할 수 있다(FR-043)

---

## 8. 성능 (SC-009a, SC-005, SC-009)

```bash
curl -o /dev/null -s -w 'latest: %{time_total}s\n' "localhost:8080/api/fx/latest?currency=USD"
curl -o /dev/null -s -w 'daily:  %{time_total}s\n' "localhost:8080/api/fx/daily?currency=USD"
curl -o /dev/null -s -w 'series: %{time_total}s\n' "localhost:8080/api/fx/series?currency=USD&from=1964-05-04&to=2026-08-29&maxPoints=2000"
```

**기대**
- 세 호출이 병렬로 나가므로 화면 완성은 가장 느린 하나에 좌우된다. 전체 3초 이내(SC-009a)
- 스프레드 저장 후 요약·표 갱신 2초 이내(SC-005)
- 차트 확대·이동·시점 지정 1초 이내(SC-009) — UI에서 수동 확인

---

## 9. 스프레드 설정과 기본값 복원 (US3 / FR-027~035)

설정 화면에서 USD 현금 살 때를 `0.0025`로 바꾸고 저장.

**기대**
- 외환 화면의 표에서 "현금 살 때" 열이 전부 커진다. 매매기준율 열은 그대로다
- 설정 화면에 "기본값과 다름" 표시가 나타난다

범위 위반:

```bash
curl -X PUT localhost:8080/api/fx/spreads/USD -d '{"cashBuy":"1.5", ...}'   # → 422
```

복원:

```bash
curl -X POST localhost:8080/api/fx/spreads/restore -d '{"currency":"USD"}'
```

**기대**
- UI에서는 되돌리기 전에 **무엇이 어떻게 바뀌는지 보여주는 확인창**이 뜬다(FR-032, W4-a)
- 취소하면 값이 그대로다
- 복원 후 응답의 값이 001 시드의 기본값과 일치한다

**부분 실패 (FR-031a)**: 전 통화 복원 중 하나가 실패하도록 유도한다(예: 해당 행을 잠근 상태로 호출).

**기대**: `restored`에 성공한 통화가, `failed`에 실패한 통화와 사유가 담긴다. 상태 코드는
`200`이며 **성공한 복원이 되돌려지지 않는다.**

---

## 10. 내려받기 (US5 / FR-044~047)

표에서 내려받기 실행.

**기대**
- 파일의 수치가 화면 표시값과 **정밀도까지** 일치한다(FR-045)
- 잠정 행을 구분할 수 있다(FR-047)
- 통화·구간·적용 스프레드가 파일에 포함된다(FR-046)

**정밀도 확인**: 파일의 매매기준율이 `1354.200000` 형태(저장 정밀도)인지, `1354.2`로 잘리지
않았는지 본다. 잘렸다면 어딘가에서 문자열이 숫자로 변환된 것이다(research R2-7).

---

## 11. 미수집 구간의 자동 수집 (FR-048)

아직 수집하지 않은 통화(예: EUR)로 전환한다.

```bash
curl -i "localhost:8080/api/fx/latest?currency=EUR"
curl -i "localhost:8080/api/fx/daily?currency=EUR"
```

**기대**
- 필요한 구간이 임계값 이하면 수집 완료 후 `200`
- 임계값을 초과하면 `202`와 `progressUrl`이 반환되고 화면이 진행 상태를 보여준다
- 응답 형식은 001의 `GET /api/fx/rates` 202와 같다

---

## 12. 헌법 준수 확인

```bash
cd backend && .venv/bin/python -m pytest --cov=src --cov-fail-under=80
.venv/bin/python -m mypy --strict src
cd ../frontend && npm run typecheck && npx vitest run
```

**추가 정적 검사** — 이번 기능이 새로 필요로 하는 것

| 확인 | 근거 |
|------|------|
| `lib/csv.ts`에 `Number(`·`parseFloat(` 없음 | 헌법 VI (research R2-7) |
| 프론트엔드에서 파생 환율을 계산하지 않음 | 헌법 VI (research R2-5) |
| `ingestion/today.py`가 커버리지를 갱신하지 않음 | FR-037b (research R2-2) |
| 미구현 자산군의 라우트·API·모델이 없음 | 헌법 IX (research R2-9) |
| 다운샘플링 후 끝점이 항상 남음 | FR-017b (research R2-4) |

네트워크를 차단한 상태에서 전체 스위트가 통과해야 한다(헌법 원칙 III).
