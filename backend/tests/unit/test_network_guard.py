"""네트워크 차단 확인 (T089) — 006, 헌법 원칙 III.

전체 스위트는 네트워크 없이 통과해야 한다. 005가 더한 소켓 가드(`tests/conftest.py`)가 006의 키움
경로도 막는지 본다 — 어댑터 한 곳에서 스텁을 빠뜨리면 조용히 진짜 호출이 나가고, 통과하므로 아무도
모른다. 키움은 토큰 발급까지 실제 계좌의 키로 나가므로 더 비싸다.
"""
from __future__ import annotations

import socket

import pytest

from src.config.settings import Settings, _Secret
from src.ingestion.kiwoom import client as kiwoom_client


def test_키움_도메인으로의_접속을_막는다() -> None:
    sock = socket.socket()
    try:
        with pytest.raises(RuntimeError, match="외부로 접속"):
            sock.connect(("api.kiwoom.com", 443))
    finally:
        sock.close()


def test_로컬_접속은_막지_않는다() -> None:
    """DB가 로컬이라 허용해야 한다. 닫힌 포트면 거절될 뿐 가드에 걸리지 않는다."""
    sock = socket.socket()
    try:
        assert sock.connect_ex(("127.0.0.1", 9)) != 0
    finally:
        sock.close()


async def test_키움_클라이언트의_실제_요청이_막힌다(monkeypatch: pytest.MonkeyPatch) -> None:
    """aiohttp가 해석한 주소로 붙는 경로까지 막히는지 본다. 문서용 주소(TEST-NET-3)라 DNS도 쓰지
    않는다."""
    monkeypatch.setitem(kiwoom_client.DOMAINS, "real", "https://203.0.113.10")
    settings = Settings(ecos_api_key=_Secret("ecos"), kiwoom_app_key=_Secret("k"),
                        kiwoom_app_secret=_Secret("s"))
    async with kiwoom_client.KiwoomClient(settings) as c:
        with pytest.raises(RuntimeError, match="외부로 접속"):
            await c.fetch_unit("KOSPI")
