"""투자 비교 설정 API·대상 수의 끝·저장 길이 (014 반복 2026-10-13 T213) — spec FR-044, FR-045,
SC-027, contracts A18·A19, data-model 18.

- `GET /api/comparison/settings` — 행이 없으면 기본(20)이고 범위·기본은 상수다(화면이 이 값으로
  그린다)
- `PUT` — JSON 정수 2~100만 저장한다. 틀리면 422 `invalid_setting`이고 저장된 값은 그대로다
- 저장한 비교의 대상 수 끝은 **설정이 아니라 100**이다 — 설정을 낮춰도 그보다 많은 비교를 저장할 수
  있다(FR-045)
- 조건 글이 65,535바이트(TEXT)면 저장되고, 넘으면 422 — MySQL에 보내지 않는다
- `comparison_setting`은 단일 행 테이블이고 머리 리비전이다. 이 경로는 비교
  경로(`/api/comparison/<자산군>/…`)에 잡히지 않는다
"""

from __future__ import annotations

import pytest
from alembic.script import ScriptDirectory
from sqlalchemy import text

from src.db.migrate import _alembic_config
from tests.integration.comparison_support import http
from tests.unit.test_comparison_target_limit import sized, stock, stock_targets

PATH = "/api/comparison/settings"
SAVED = "/api/comparison/saved"
DEFAULT = {"maxTargets": 20, "defaultMaxTargets": 20, "minTargets": 2, "limitTargets": 100}


class Test설정:
    async def test_행이_없으면_기본이다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            response = await client.get(PATH)
        assert (response.status_code, response.json()) == (200, DEFAULT)

    async def test_저장하고_다시_읽는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            saved = await client.put(PATH, json={"maxTargets": 100})
            again = await client.get(PATH)
            lowered = await client.put(PATH, json={"maxTargets": 2})
        assert (saved.status_code, saved.json()) == (200, {**DEFAULT, "maxTargets": 100})
        assert again.json() == {**DEFAULT, "maxTargets": 100}
        assert lowered.json() == {**DEFAULT, "maxTargets": 2}

    @pytest.mark.parametrize("value", [1, 101, True, 20.5, "20", None])
    async def test_틀린_값은_422이고_저장된_값은_그대로다(  # type: ignore[no-untyped-def]
            self, session_factory, value: object) -> None:
        async with http(session_factory) as client:
            await client.put(PATH, json={"maxTargets": 55})
            response = await client.put(PATH, json={"maxTargets": value})
            after = await client.get(PATH)
        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "invalid_setting"
        assert "최대 대상 수는 2~100 사이의 정수여야 합니다" in body["message"]
        assert after.json()["maxTargets"] == 55

    async def test_칸이_없으면_422다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            response = await client.put(PATH, json={"limit": 30})
            after = await client.get(PATH)
        assert (response.status_code, response.json()["status"]) == (422, "invalid_setting")
        assert after.json() == DEFAULT

    async def test_한_행만_쓴다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            for value in (30, 40, 50):
                await client.put(PATH, json={"maxTargets": value})
        async with session_factory() as s:
            rows = (await s.execute(text("SELECT id, max_targets FROM comparison_setting"))).all()
        assert [tuple(r) for r in rows] == [(1, 50)]


class Test저장한_비교의_끝:
    async def test_대상_100개를_저장하고_그대로_불러온다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        condition = stock(stock_targets(100))
        async with http(session_factory) as client:
            created = await client.post(SAVED, json={"name": "주식 100개", "condition": condition})
            listed = await client.get(SAVED)
        assert created.status_code == 201
        assert listed.json()["entries"][0]["condition"] == condition

    async def test_설정을_낮춰도_그보다_많은_비교를_저장한다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            await client.put(PATH, json={"maxTargets": 10})
            created = await client.post(
                SAVED, json={"name": "30개", "condition": stock(stock_targets(30))})
        assert created.status_code == 201

    async def test_101개는_422다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            await client.put(PATH, json={"maxTargets": 100})
            response = await client.post(
                SAVED, json={"name": "101개", "condition": stock(stock_targets(101))})
            listed = await client.get(SAVED)
        assert response.status_code == 422
        assert response.json() == {"status": "invalid_comparison",
                                   "message": "targets: 2~100개여야 합니다: 101개"}
        assert listed.json() == {"entries": []}

    async def test_조건_글_65535바이트는_TEXT_열에_들어간다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        condition = sized(65_535)
        async with http(session_factory) as client:
            created = await client.post(SAVED, json={"name": "큰 비교", "condition": condition})
            listed = await client.get(SAVED)
        assert created.status_code == 201
        assert listed.json()["entries"][0]["condition"] == condition
        async with session_factory() as s:
            stored = (await s.execute(
                text("SELECT LENGTH(`condition`) FROM saved_comparison"))).scalar()
        assert stored == 65_535

    async def test_넘으면_422이고_저장하지_않는다(self, session_factory) -> None:  # type: ignore[no-untyped-def]
        async with http(session_factory) as client:
            response = await client.post(
                SAVED, json={"name": "큰 비교", "condition": sized(65_536)})
            listed = await client.get(SAVED)
        assert response.status_code == 422
        body = response.json()
        assert body["status"] == "invalid_comparison"
        assert body["message"].startswith("condition: ")
        assert listed.json() == {"entries": []}


class Test스키마:
    async def test_열과_형(self, engine) -> None:  # type: ignore[no-untyped-def]
        async with engine.connect() as conn:
            # 원시 SQL — information_schema의 열 정보는 ORM으로 표현할 수 없다(테스트 전용 조회).
            rows = (await conn.execute(text(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = 'comparison_setting'"))).all()
        assert {r[0]: (r[1], r[2]) for r in rows} == {
            "id": ("smallint", "NO"), "max_targets": ("smallint", "NO"),
            "updated_at": ("datetime", "NO")}

    def test_리비전은_기준금리_뒤의_머리다(self) -> None:
        script = ScriptDirectory.from_config(_alembic_config())
        head = script.get_revision(script.get_current_head())
        assert head is not None
        assert head.down_revision == "e9f3b7c2a4d1"
        assert "투자 비교 설정" in (head.doc or "")
