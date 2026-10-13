"""비교 조건 검증의 끝과 저장 길이 (014 반복 2026-10-13 T213) — spec FR-045, contracts A19,
data-model 18.2·18.3.

- 대상 수의 끝은 **2~100개**(예금 ≤5)다 — 013 FR-004의 10개를 대체한다. 끝은 설정 값이 아니다(설정은
  화면의 더하기 한도) — 설정을 낮춰도 저장한 비교를 다시 저장할 수 있어야 한다(FR-045 실패 양상
  *늦게 일어남*)
- 저장 열은 MySQL TEXT(65,535바이트)다. 직렬화한 조건 글(UTF-8 — 한글 3바이트)이 그것을 넘으면
  **저장소를 부르지 않고** 422로 알린다 — 보내면 MySQL 엄격 모드가 500으로 거절해 무엇이 틀렸는지 알
  수 없다
"""

from __future__ import annotations

import datetime as dt
import json
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import InvalidComparison
from src.api.services import saved_comparison
from src.api.services.comparison_conditions import validate_condition
from src.repository.saved_comparison import StoredComparison

#: 이름 하나에 더할 수 있는 바이트 — 처음 `a` 한 자 + 한글 197자 + 끝 `a` 둘이면 200자
#: (`MAX_TEXT`) 안이다.
_PAD_LIMIT = 591
Target = dict[str, object]


def stock_targets(count: int) -> list[Target]:
    return [{"market": "KRX", "symbol": f"{i:06d}.KS", "name": f"종목{i}", "currency": "KRW"}
            for i in range(count)]


def crypto_targets(count: int) -> list[Target]:
    return [{"coinId": i + 1, "symbol": f"C{i}", "name": f"Coin {i}", "nameKo": None,
             "currency": "USD"} for i in range(count)]


def stock(targets: list[Target]) -> dict[str, object]:
    return {"v": 1, "asset": "stock", "method": "lump_sum", "frequency": None,
            "start": "2020-01-02", "amount": "10000000", "principalCurrency": "KRW",
            "reinvest": True, "targets": targets}


def size_of(condition: dict[str, object]) -> int:
    return len(validate_condition(condition).text.encode("utf-8"))


def count_of(condition: dict[str, object]) -> int:
    targets = validate_condition(condition).body["targets"]
    assert isinstance(targets, list)
    return len(targets)


def sized(total: int) -> dict[str, object]:
    """조건 글이 꼭 `total`바이트(UTF-8)인 주식 대상 100개 조건 — 이름 길이로 맞춘다."""
    targets: list[Target] = [
        {"market": "KRX", "symbol": f"{i:06d}.KS", "name": "a", "currency": "KRW"}
        for i in range(100)]
    extra = total - size_of(stock(targets))
    assert extra >= 0
    for target in targets:
        add = min(extra, _PAD_LIMIT)
        korean, ascii_ = divmod(add, 3)
        target["name"] = "a" + "가" * korean + "a" * ascii_
        extra -= add
    assert extra == 0, "이름 100개로 맞출 수 없다 — 기준 글이 너무 짧다"
    condition = stock(targets)
    assert size_of(condition) == total
    return condition


def rejected(condition: dict[str, object]) -> str:
    with pytest.raises(InvalidComparison) as caught:
        validate_condition(condition)
    return str(caught.value)


class Test대상_수:
    def test_주식_대상_100개는_된다(self) -> None:
        assert count_of(stock(stock_targets(100))) == 100

    @pytest.mark.parametrize("count", [101, 150])
    def test_101개_이상은_거절한다(self, count: int) -> None:
        assert rejected(stock(stock_targets(count))) == f"targets: 2~100개여야 합니다: {count}개"

    def test_1개는_거절한다(self) -> None:
        assert rejected(stock(stock_targets(1))) == "targets: 2~100개여야 합니다: 1개"

    def test_가상자산도_100개가_끝이다(self) -> None:
        base = {**stock([]), "asset": "crypto", "reinvest": None}
        assert count_of({**base, "targets": crypto_targets(100)}) == 100
        assert rejected({**base, "targets": crypto_targets(101)}) == (
            "targets: 2~100개여야 합니다: 101개")

    def test_예금은_다섯이_끝이다(self) -> None:
        institutions = ["commercial_bank", "savings_bank", "credit_union", "mutual_finance",
                        "saemaul"]
        base = {**stock([]), "asset": "deposit", "method": "deposit", "amount": "1000000",
                "reinvest": None}
        five = [{"institution": i} for i in institutions]
        assert count_of({**base, "targets": five}) == 5
        six = [*five, {"institution": "commercial_bank"}]
        assert rejected({**base, "targets": six}) == "targets: 2~5개여야 합니다: 6개"


class FakeRepo:
    def __init__(self) -> None:
        self.rows: list[StoredComparison] = []

    async def list_entries(self, session: object) -> list[StoredComparison]:
        return list(reversed(self.rows))

    async def add(self, session: object, *, name: str, asset: str, condition: str,
                  saved_at: dt.datetime) -> int:
        self.rows.append(StoredComparison(len(self.rows) + 1, name, asset, condition, saved_at))
        return len(self.rows)

    async def remove(self, session: object, comparison_id: int) -> None:
        raise AssertionError("지우지 않는다")


class FakeSession:
    async def commit(self) -> None:
        return None


async def save(repo: FakeRepo, name: str, condition: dict[str, object]) -> dict[str, object]:
    session = cast(AsyncSession, FakeSession())
    return await saved_comparison.save(session, repo, {"name": name, "condition": condition})


class Test저장_길이:
    def test_끝은_TEXT_열의_크기다(self) -> None:
        assert saved_comparison.MAX_CONDITION_BYTES == 65_535

    async def test_65535바이트는_저장한다(self) -> None:
        repo = FakeRepo()
        condition = sized(65_535)
        body = await save(repo, "큰 비교", condition)
        assert len(repo.rows) == 1
        assert len(repo.rows[0].condition.encode("utf-8")) == 65_535
        assert json.loads(repo.rows[0].condition)["targets"] == condition["targets"]
        entry = body["entry"]
        assert isinstance(entry, dict)
        assert entry["condition"]["targets"] == condition["targets"]

    @pytest.mark.parametrize("total", [65_536, 65_600])
    async def test_넘으면_저장소를_부르지_않고_거절한다(self, total: int) -> None:
        repo = FakeRepo()
        with pytest.raises(InvalidComparison) as caught:
            await save(repo, "큰 비교", sized(total))
        message = str(caught.value)
        assert message.startswith("condition: ")
        assert f"{total:,}바이트" in message
        assert "65,535바이트까지" in message
        assert repo.rows == []

    async def test_대상_100개의_현실_크기는_끝_안이다(self) -> None:
        # 실측(T218)과 같은 꼴 — 미국 ETF 이름(영문 40자 안팎)·심볼. 대상당 약 100바이트다
        targets: list[Target] = [
            {"market": "NYSE", "symbol": f"ETF{i:03d}",
             "name": f"Vanguard Example Index Fund ETF Shares {i}", "currency": "USD"}
            for i in range(100)]
        assert size_of(stock(targets)) < 20_000
        repo = FakeRepo()
        await save(repo, "주식 100개", stock(targets))
        assert len(repo.rows) == 1
