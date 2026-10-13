"""투자 비교 설정의 검증·본문 (014 반복 2026-10-13 T213) — spec FR-044, contracts A18, data-model
18.

최대 대상 수는 **JSON 정수 2~100**이고 기본은 20이다(행이 없으면 20). 범위 밖·정수가 아닌 값은
저장하지 않는다 — 조용히 기본값이나 가까운 값으로 바꾸면 사용자가 친 값과 다른 한도가 걸린다(FR-044
실패 양상 *조용히 틀림*). 불리언은 Python에서 `int`의 하위형이라 따로 막는다(`true` → 1). 설정의 위
끝은 비교 조건 검증의 끝과 같은 상수다 — 둘이 어긋나면 설정한 수만큼 더한 비교를 저장할 수 없다.
"""

from __future__ import annotations

import pytest

from src.api.errors import InvalidSetting
from src.api.services import comparison_conditions
from src.api.services.comparison_settings import (
    DEFAULT_SETTING,
    MAX_SETTING,
    MIN_SETTING,
    parse_max_targets,
    settings_body,
)


class Test범위:
    def test_기본은_20이고_범위는_2부터_100이다(self) -> None:
        assert (DEFAULT_SETTING, MIN_SETTING, MAX_SETTING) == (20, 2, 100)

    def test_설정의_끝은_비교_조건_검증의_끝과_같은_상수다(self) -> None:
        assert MIN_SETTING == comparison_conditions.MIN_TARGETS
        assert MAX_SETTING == comparison_conditions.MAX_TARGETS

    @pytest.mark.parametrize("value", [2, 20, 55, 100])
    def test_범위_안의_정수는_그대로다(self, value: int) -> None:
        assert parse_max_targets({"maxTargets": value}) == value

    @pytest.mark.parametrize("value", [1, 0, -5, 101, 1000, True, False, 20.5, 20.0, "20", None,
                                       [20], {"n": 20}])
    def test_범위_밖이거나_정수가_아니면_거절한다(self, value: object) -> None:
        with pytest.raises(InvalidSetting) as caught:
            parse_max_targets({"maxTargets": value})
        assert "최대 대상 수는 2~100 사이의 정수여야 합니다" in str(caught.value)

    @pytest.mark.parametrize("payload", [{}, {"maxTarget": 20}, [20], "20", None])
    def test_칸이_없거나_본문이_객체가_아니면_거절한다(self, payload: object) -> None:
        with pytest.raises(InvalidSetting) as caught:
            parse_max_targets(payload)
        assert "최대 대상 수" in str(caught.value)


class Test본문:
    def test_행이_없으면_기본이다(self) -> None:
        assert settings_body(None) == {
            "maxTargets": 20, "defaultMaxTargets": 20, "minTargets": 2, "limitTargets": 100}

    def test_저장된_값은_maxTargets뿐이고_나머지는_상수다(self) -> None:
        assert settings_body(55) == {
            "maxTargets": 55, "defaultMaxTargets": 20, "minTargets": 2, "limitTargets": 100}
