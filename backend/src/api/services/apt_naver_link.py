"""부동산 단지의 Npay 부동산 단지 화면 주소 (010 반복 3, FR-029, research R10-19, contracts/rest-api
반복 3).

단지 이름에서 Npay 부동산 단지 화면(`fin.land.naver.com/complexes/{번호}`)을 열려면 네이버 단지
번호가 필요한데 공개된 방법이 없다 — 검색 칸의 단지 자동완성(공개되지 않은 내부 API, 헌법 원칙 II
이탈)으로 **한 단지에 한 번** 찾아 저장한다.

- 고르기(`pick_naver_complex`, 순수 함수): 같은 법정동 코드 → 정규화한 이름이 정확히 같은 후보 하나
  → 없으면
  한쪽이 다른 쪽을 품는 후보가 하나뿐일 때만. 그 밖은 못 찾음 — 틀린 단지로 보내느니 검색으로 연다
- 검색어: `{법정동 이름} {정규화한 단지명}`, 같은 법정동 후보가 없으면 정규화한 단지명만으로 한 번
  더
- 찾음은 다시 부르지 않는다. 못 찾음은 정해진 날 수(설정) 뒤 다시 찾는다. **실패는 저장하지 않는다**
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import Final, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.api.errors import UnknownComplex
from src.config.settings import Settings
from src.db.models import AptComplexNaver
from src.ingestion.naver_land.client import ComplexSearchFetch
from src.ingestion.naver_land.errors import NaverLandError
from src.ingestion.naver_land.parse import NaverComplexCandidate
from src.repository import apt_complex, apt_naver, apt_region

Json = dict[str, object]

#: Npay 부동산 단지 화면.
COMPLEX_URL: Final = "https://fin.land.naver.com/complexes/{}"

_PAREN = re.compile(r"\([^)]*\)")
_SPACE = re.compile(r"\s+")
_SUFFIX = "아파트"

_log = logging.getLogger(__name__)


class ComplexSearch(Protocol):
    """단지 자동완성 — 실제는 `NaverLandClient`, 테스트는 가짜다."""

    async def search_complexes(self, keyword: str) -> ComplexSearchFetch: ...


_shared: ComplexSearch | None = None


def set_shared_client(client: ComplexSearch | None) -> None:
    """앱 수명(lifespan)이 클라이언트 하나를 맡긴다 — 요청 사이 최소 간격을 모든 요청이 함께
    지킨다."""
    global _shared
    _shared = client


def get_naver_land_client() -> ComplexSearch:
    if _shared is None:
        raise RuntimeError("Npay 부동산 클라이언트가 없습니다 — 앱 수명(lifespan) 밖입니다.")
    return _shared


def normalize_complex_name(name: str) -> str:
    """공백·괄호와 그 안·끝의 "아파트"를 뺀다. 이름 전체가 "아파트"면 그대로 둔다 — 빈 이름은
    무엇이든 품는다."""
    text = _SPACE.sub("", _PAREN.sub("", name))
    if text.endswith(_SUFFIX) and len(text) > len(_SUFFIX):
        text = text[: -len(_SUFFIX)]
    return text


def search_keywords(umd_name: str, name: str) -> list[str]:
    """보낼 검색어 순서 — 법정동 이름을 붙인 것, 다음에 단지명만."""
    plain = normalize_complex_name(name)
    keywords = ([f"{umd_name} {plain}"] if umd_name else []) + [plain]
    return list(dict.fromkeys(keywords))


def pick_naver_complex(candidates: list[NaverComplexCandidate], *, umd_code: str,
                       name: str) -> NaverComplexCandidate | None:
    """같은 법정동에서 이름이 맞는 후보 하나. 없거나 여럿이면 `None`(못 찾음)."""
    ours = normalize_complex_name(name)
    same = [c for c in candidates if c.legal_division_code == umd_code]
    exact = [c for c in same if normalize_complex_name(c.name) == ours]
    if exact:
        return exact[0] if len(exact) == 1 else None
    partial = [c for c in same if _overlaps(normalize_complex_name(c.name), ours)]
    return partial[0] if len(partial) == 1 else None


def _overlaps(theirs: str, ours: str) -> bool:
    return bool(theirs) and bool(ours) and (theirs in ours or ours in theirs)


def _body(complex_id: int, saved: AptComplexNaver) -> Json:
    found = saved.status == apt_naver.FOUND and saved.naver_complex_no is not None
    return {"complexId": complex_id, "status": apt_naver.FOUND if found else apt_naver.NOT_FOUND,
            "url": COMPLEX_URL.format(saved.naver_complex_no) if found else None, "reason": None}


def _fresh(saved: AptComplexNaver, *, settings: Settings, now: dt.datetime) -> bool:
    """저장한 답을 그대로 쓸지. 찾음은 늘, 못 찾음은 정해진 날 수 안에서만."""
    if saved.status == apt_naver.FOUND:
        return True
    return now - saved.checked_at < dt.timedelta(days=settings.naver_land_recheck_days)


async def naver_link(session: AsyncSession, complex_id: int, *, client: ComplexSearch,
                     settings: Settings, now: dt.datetime) -> Json:
    """`GET /api/realestate/complexes/{complexId}/naver`의 본문. 합쳐진 단지는 합쳐 받은 단지로
    찾는다."""
    row = await apt_complex.resolve(session, complex_id)
    if row is None:
        raise UnknownComplex(f"모르는 단지입니다: {complex_id}")
    # 커밋하면 ORM 객체가 만료된다 — 뒤에서 쓸 값은 지금 잡아 둔다(만료된 속성은 동기로 다시 읽으려
    # 한다).
    target, umd_code, name = row.id, row.umd_code, row.name
    saved = await apt_naver.get(session, target)
    if saved is not None and _fresh(saved, settings=settings, now=now):
        return _body(complex_id, saved)

    region = await apt_region.current(session, umd_code)
    umd_name = region.name if region is not None else ""
    fetch: ComplexSearchFetch | None = None
    try:
        for keyword in search_keywords(umd_name, name):
            fetch = await client.search_complexes(keyword)
            if any(c.legal_division_code == umd_code for c in fetch.candidates):
                break
    except NaverLandError as exc:
        # 저장하지 않는다 — 다음 요청에서 다시 찾는다. 화면은 네이버 검색으로 연다.
        _log.warning("Npay 부동산 단지 번호를 찾지 못했습니다(%s): 단지 %s", exc.kind, target)
        return {"complexId": complex_id, "status": "failed", "url": None, "reason": exc.kind}
    if fetch is None:  # 검색어가 하나도 없다 — 단지명이 비어 있지 않은 한 오지 않는다
        return {"complexId": complex_id, "status": apt_naver.NOT_FOUND, "url": None, "reason": None}

    picked = pick_naver_complex(fetch.candidates, umd_code=umd_code, name=name)
    await apt_naver.save(session, target, number=picked.number if picked else None,
                         name=picked.name if picked else None, keyword=fetch.keyword,
                         raw=fetch.raw, now=now)
    await session.commit()
    stored = await apt_naver.get(session, target)
    assert stored is not None
    return _body(complex_id, stored)
