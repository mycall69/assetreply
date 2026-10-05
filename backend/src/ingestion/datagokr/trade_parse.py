"""상세 실거래 파서 (009 T011, FR-008, FR-009, FR-014, FR-019, research R9-1·R9-4).

국토교통부 아파트 매매 실거래가 상세 자료(`RTMSDataSvcAptTradeDev`)의 XML 한 쪽을 읽는다. 응답은
`response/header/resultCode`(정상 `000`), `response/body/items/item[]`, `body/totalCount`·`pageNo`·
`numOfRows`다. **빈 값은 공백 한 칸**(`<aptDong> </aptDong>`)이라 모든 값의 앞뒤 공백을 지운다(T001
실측).

- 금액은 만원 쉼표 문자열(`"75,000"`) → 원 단위 정수(× 10,000, FR-019)
- 전용면적은 문자열 그대로 `Decimal` — 출처가 **소수 4자리까지** 준다(`84.9725`). 저장 자릿수
  (`DECIMAL(9,4)`)를 넘으면 반올림하지 않고 형식 오류다
- 법정동 코드 = `sggCd + umdCd`(10자리). 해제는 `cdealType = O`, 해제 신고일은 `YY.MM.DD`
- 거래 유형(`dealingGbn`)은 2021-11 이전 계약이 빈 값 → `None`
- 받은 행 수가 그 쪽의 몫(`totalCount`·`numOfRows`·`pageNo`로 정해진다)과 다르면 잘림 — 형식 오류.
  **행 하나라도 읽지 못하면 응답 전체가 형식 오류**다 — 일부만 저장하면 그 달의 건수·평균이 조용히
  틀린다
- 행의 시·군·구와 계약 월이 요청과 다르면 형식 오류 — 다른 달의 거래를 그 달로 세지 않는다
- XML이 아니면(점검 안내 등) 연결 오류 — 다시 시도한다

**순번(`occurrence`)은 여기서 매기지 않는다.** 키 필드가 모두 같은 행이 한 계약 월의 1쪽과 2쪽에
나뉘어 올 수 있어(2020-06 실측), 그 달의 쪽을 모두 받은 뒤 `number_trades`가 이어 매긴다(R9-4).

XML은 표준 라이브러리로 읽는다 — 외부 엔터티를 풀지 않고, expat이 엔터티 폭증을 막는다. 문서 형식
선언(`<!DOCTYPE`)이 든 응답은 읽지 않는다.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime as dt
import re
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from src.ingestion.datagokr.errors import DataGoKrFormatError, DataGoKrUnavailable
from src.ingestion.protocols import AptTrade

_OK: Final = "000"
_MAN_WON: Final = 10_000
#: 면적의 저장 자릿수(`DECIMAL(9,4)`) — 정수부 5자리, 소수부 4자리.
_AREA = re.compile(r"\d{1,5}(?:\.\d{1,4})?")
_AMOUNT = re.compile(r"\d{1,3}(?:,\d{3})*")
_CANCEL_DAY = re.compile(r"(\d{2})\.(\d{2})\.(\d{2})")
_FIVE_DIGITS = re.compile(r"\d{5}")
_INTEGER = re.compile(r"-?\d+")
_CANCELLED: Final = "O"
#: 저장 열의 길이(data-model 3절) — 넘으면 저장할 수 없으므로 형식 오류.
_MAX_LENGTH: Final = {"aptSeq": 20, "aptNm": 80, "aptDong": 20, "jibun": 20, "dealingGbn": 8}


@dataclass(frozen=True, slots=True)
class TradeRow:
    """출처의 한 행을 정규화한 것. 순번은 아직 없다 — `number_trades`가 계약 월 단위로 매긴다."""

    lawd_cd: str
    deal_ym: str
    deal_date: dt.date
    apt_seq: str
    umd_code: str
    jibun: str
    apt_name: str
    apt_dong: str
    floor: int
    excl_area: Decimal
    amount: int
    dealing_type: str | None
    cancelled: bool
    cancelled_on: dt.date | None
    build_year: int | None

    @property
    def key(self) -> tuple[object, ...]:
        """거래를 가르는 필드(R9-4). 바뀔 수 있는 필드(해제·거래 유형)는 넣지 않는다."""
        return (self.lawd_cd, self.deal_date, self.apt_seq, self.apt_dong, self.floor,
                self.excl_area, self.amount)


@dataclass(frozen=True, slots=True)
class TradePage:
    total_count: int
    page_no: int
    rows: tuple[TradeRow, ...]


def _bad(message: str) -> DataGoKrFormatError:
    return DataGoKrFormatError(f"실거래 {message}")


def _child(parent: ET.Element, name: str) -> str:
    element = parent.find(name)
    if element is None:
        raise _bad(f"응답에 {name}이(가) 없습니다")
    return (element.text or "").strip()


def _whole(parent: ET.Element, name: str) -> int:
    value = _child(parent, name)
    if not value.isdigit():
        raise _bad(f"응답의 {name} 값을 읽을 수 없습니다: {value!r}")
    return int(value)


class _Item:
    """한 행의 값 읽기 — 실패하면 어느 필드인지 문구에 남긴다."""

    def __init__(self, element: ET.Element) -> None:
        self._element = element

    def text(self, name: str, *, required: bool = False) -> str:
        value = _child(self._element, name)
        if required and not value:
            raise _bad(f"행의 {name} 값이 비었습니다")
        limit = _MAX_LENGTH.get(name)
        if limit is not None and len(value) > limit:
            raise _bad(f"행의 {name} 값이 저장 길이({limit})를 넘습니다: {value!r}")
        return value

    def matching(self, name: str, pattern: re.Pattern[str]) -> str:
        value = self.text(name)
        if not pattern.fullmatch(value):
            raise _bad(f"행의 {name} 값을 읽을 수 없습니다: {value!r}")
        return value


def _deal_date(item: _Item) -> dt.date:
    year, month, day = (int(item.matching(n, _INTEGER))
                        for n in ("dealYear", "dealMonth", "dealDay"))
    try:
        return dt.date(year, month, day)
    except ValueError as exc:
        raise _bad(f"행의 계약일을 읽을 수 없습니다: {year}-{month}-{day}") from exc


def _area(item: _Item) -> Decimal:
    area = Decimal(item.matching("excluUseAr", _AREA))
    if area <= 0:
        raise _bad(f"행의 전용면적이 0입니다: {area}")
    return area


def _amount(item: _Item) -> int:
    man_won = int(item.matching("dealAmount", _AMOUNT).replace(",", ""))
    if man_won <= 0:
        raise _bad("행의 거래금액이 0입니다")
    return man_won * _MAN_WON


def _cancellation(item: _Item) -> tuple[bool, dt.date | None]:
    kind = item.text("cdealType")
    if not kind:
        return False, None
    if kind != _CANCELLED:
        raise _bad(f"행의 해제 여부를 읽을 수 없습니다: {kind!r}")
    day = item.text("cdealDay")
    found = _CANCEL_DAY.fullmatch(day)
    if found is None:
        raise _bad(f"해제 행의 해제 신고일을 읽을 수 없습니다: {day!r}")
    yy, mm, dd = (int(part) for part in found.groups())
    try:
        return True, dt.date(2000 + yy, mm, dd)
    except ValueError as exc:
        raise _bad(f"해제 행의 해제 신고일을 읽을 수 없습니다: {day!r}") from exc


def _row(element: ET.Element, lawd_cd: str, ym: str) -> TradeRow:
    item = _Item(element)
    sgg = item.matching("sggCd", _FIVE_DIGITS)
    if sgg != lawd_cd:
        raise _bad(f"요청한 시·군·구({lawd_cd})와 다른 행입니다: {sgg}")
    deal_date = _deal_date(item)
    deal_ym = f"{deal_date.year:04d}{deal_date.month:02d}"
    if deal_ym != ym:
        raise _bad(f"요청한 계약 월({ym})과 다른 행입니다: {deal_ym}")
    cancelled, cancelled_on = _cancellation(item)
    build_year = item.text("buildYear")
    if build_year and not build_year.isdigit():
        raise _bad(f"행의 buildYear 값을 읽을 수 없습니다: {build_year!r}")
    return TradeRow(
        lawd_cd=sgg, deal_ym=deal_ym, deal_date=deal_date,
        apt_seq=item.text("aptSeq", required=True),
        umd_code=sgg + item.matching("umdCd", _FIVE_DIGITS),
        jibun=item.text("jibun"), apt_name=item.text("aptNm"), apt_dong=item.text("aptDong"),
        floor=int(item.matching("floor", _INTEGER)), excl_area=_area(item), amount=_amount(item),
        dealing_type=item.text("dealingGbn") or None, cancelled=cancelled,
        cancelled_on=cancelled_on, build_year=int(build_year) if build_year else None,
    )


def parse_trades(body: str, *, lawd_cd: str, ym: str) -> TradePage:
    """상세 실거래 한 쪽. `lawd_cd`·`ym`은 요청한 시·군·구(5자리)와 계약 월(`YYYYMM`)이다."""
    if "<!DOCTYPE" in body:
        raise _bad("응답에 문서 형식 선언이 있습니다")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise DataGoKrUnavailable("실거래 응답이 XML이 아닙니다") from exc
    if root.tag != "response":
        if root.tag.lower() == "html":
            raise DataGoKrUnavailable("실거래 응답이 XML이 아닙니다(HTML)")
        raise _bad(f"응답의 모양이 다릅니다: {root.tag}")
    header, part = root.find("header"), root.find("body")
    if header is None or part is None:
        raise _bad("응답의 모양이 다릅니다")
    code = _child(header, "resultCode")
    if code != _OK:
        raise _bad(f"결과 코드 {code}")
    items = part.find("items")
    if items is None:
        raise _bad("응답에 items가 없습니다")
    total, page_no, per_page = (_whole(part, n) for n in ("totalCount", "pageNo", "numOfRows"))
    if page_no < 1 or per_page < 1:
        raise _bad(f"응답의 쪽 정보를 읽을 수 없습니다: {page_no}/{per_page}")
    rows = tuple(_row(element, lawd_cd, ym) for element in items.findall("item"))
    expected = max(0, min(per_page, total - (page_no - 1) * per_page))
    if len(rows) != expected:
        raise _bad(f"응답이 잘렸습니다 — {page_no}쪽 {expected}행 중 {len(rows)}행")
    return TradePage(total, page_no, rows)


_ROW_FIELDS: Final = tuple(field.name for field in dataclasses.fields(TradeRow))


def number_trades(rows: Iterable[TradeRow]) -> tuple[AptTrade, ...]:
    """한 계약 월의 행(쪽을 차례로 이은 것)에 순번을 매긴다 — 키 필드가 같은 행마다 0, 1, …

    같은 값의 행은 서로 바꿔도 집계가 같으므로, 같은 달을 다시 받아도 같은 순번이 같은 거래에
    돌아간다(R9-4).
    """
    seen: collections.Counter[tuple[object, ...]] = collections.Counter()
    numbered: list[AptTrade] = []
    for row in rows:
        values = {name: getattr(row, name) for name in _ROW_FIELDS}
        numbered.append(AptTrade(**values, occurrence=seen[row.key]))
        seen[row.key] += 1
    return tuple(numbered)
