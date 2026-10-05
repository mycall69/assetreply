"""공공데이터포털 픽스처에 인증키가 없다 (T008) — 009 FR-013, SC-011.

픽스처는 응답 본문만 저장했다(요청 URL에는 키가 질의 문자열로 들어간다). 저장할 때 검사했지만, 새
픽스처를 받을 때마다 이 테스트가 다시 본다 — 압축한 원본(`.gz`)은 풀어서 본다. 키가 없는 환경(CI
등)에서는 건너뛴다.
"""
from __future__ import annotations

import gzip
import os
import urllib.parse
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "apt"


def _texts() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(FIXTURES.iterdir()):
        raw = path.read_bytes()
        if path.suffix == ".gz":
            raw = gzip.decompress(raw)
        found.append((path.name, raw.decode("utf-8", errors="ignore")))
    return found


def test_픽스처가_있다() -> None:
    names = {name for name, _ in _texts()}
    expected = {"region_seoul.json", "kapt_list_1171010700.json", "gateway_30.xml", "README.md"}
    assert expected <= names


def test_픽스처에_인증키가_없다() -> None:
    key = os.environ.get("DATA_API_KEY", "")
    if not key:
        pytest.skip("DATA_API_KEY가 없는 환경 — 저장할 때 검사했다")
    forms = {key, urllib.parse.quote(key, safe=""), urllib.parse.unquote(key)}
    leaked = [name for name, text in _texts() if any(form in text for form in forms)]
    assert leaked == []
