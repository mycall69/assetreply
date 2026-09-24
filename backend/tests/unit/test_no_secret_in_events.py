"""비밀값 차단 정적·동적 검사 (T075) — FR-020, SC-009.

차단은 **이벤트를 만드는 지점**에서 한다. 포매터에서 걸러내려면 어떤 필드가 비밀인지
아는 지식이 두 곳에 흩어지고, 새 싱크가 늘 때마다 같은 처리를 반복해야 한다.
"""
from __future__ import annotations

import pathlib

from src.observability.events import (
    CHUNK_FAILED,
    CollectionEvent,
    event_field_names,
    mask_secrets,
)

SRC = pathlib.Path(__file__).resolve().parents[2] / "src"


class Test필드_설계:
    def test_비밀값을_담을_필드가_없다(self) -> None:
        names = event_field_names()
        for token in ("key", "secret", "token", "password", "auth", "credential"):
            assert not any(token in n.lower() for n in names), token


class Test마스킹:
    def test_키처럼_보이는_토큰을_가린다(self) -> None:
        got = mask_secrets("요청 실패: https://example.com/api/X/ABCD1234EFGH5678/json")
        assert "ABCD1234EFGH5678" not in got  # type: ignore[operator]
        assert "***" in got  # type: ignore[operator]

    def test_한글_메시지는_건드리지_않는다(self) -> None:
        msg = "응답이 유효하지 않습니다"
        assert mask_secrets(msg) == msg

    def test_날짜는_가리지_않는다(self) -> None:
        msg = "2024-03-16~2025-03-15 구간 실패"
        assert mask_secrets(msg) == msg

    def test_None은_None이다(self) -> None:
        assert mask_secrets(None) is None

    def test_생성_시점에_적용된다(self) -> None:
        e = CollectionEvent(job_id=1, currency="USD", kind=CHUNK_FAILED,
                            detail="key=ABCD1234EFGH5678XYZ")
        assert "ABCD1234EFGH5678XYZ" not in (e.detail or "")


class Test소스_검사:
    def test_소스에_인증_키가_하드코딩되지_않았다(self) -> None:
        """헌법 원칙 II — 비밀값은 설정으로만 들어온다."""
        import re

        # 16자 이상 영숫자 혼합 리터럴을 찾는다. 설정 키 이름은 대문자·밑줄이라 걸리지 않는다.
        pattern = re.compile(r'["\'](?=[A-Za-z0-9]*[a-z])(?=[A-Za-z0-9]*\d)[A-Za-z0-9]{24,}["\']')
        offenders = [
            f"{p.relative_to(SRC)}:{i}"
            for p in SRC.rglob("*.py")
            for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if pattern.search(line) and "revision" not in line and "down_revision" not in line
        ]
        assert offenders == [], f"하드코딩 의심: {offenders}"
