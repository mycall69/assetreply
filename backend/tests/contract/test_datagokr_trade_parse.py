"""상세 실거래 파서 계약 테스트 (T004) — 009 FR-008, FR-009, FR-014, FR-019, research R9-1·R9-4.

T001의 실제 응답(`fixtures/apt/README.md` — 송파구 `11710` 2020-01~2023-09, 2005-11·12, 미래 달,
춘천)으로 본다:

- 금액은 만원 쉼표 문자열(`"75,000"`) → **원 단위 정수**(× 10,000). 면적은 문자열 그대로 `Decimal` —
  출처가 **소수 4자리까지** 준다(`84.9725`, T001 실측)
- 빈 값은 공백 한 칸이다(`<aptDong> </aptDong>`) — 동은 빈 문자열, 거래 유형은 `None`
- 법정동 코드 = `sggCd + umdCd`(10자리). 지번은 `jibun` 그대로(본번·부번에서 앞의 0을 지운 것과
  같다)
- 해제는 `cdealType = O`, 해제 신고일은 `YY.MM.DD`
- 키 필드가 모두 같은 행은 **계약 월 안의 순번**(`occurrence`)으로 가른다 — 2쪽짜리 달은 쪽을 건너
  이어진다(R9-4). 현진타워 2020-02-29 7층 31.02㎡ 2억 8천은 해제 1건과 정상 1건이다
- 받은 행 수가 그 쪽의 몫(`totalCount`·`numOfRows`·`pageNo`)과 다르면 **잘림 — 형식 오류**. 행
  하나라도
  읽지 못하면 **응답 전체가 형식 오류**(일부만 저장하지 않는다)
- 게이트웨이 응답은 클라이언트가 실패 종류로 바꾼다 — 사유 30 인증, 22 한도, 12 형식
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import gzip
from decimal import Decimal

import pytest

from src.config.settings import _Secret, load_settings
from src.ingestion.datagokr.client import DataGoKrClient
from src.ingestion.datagokr.errors import (
    DataGoKrAuthError,
    DataGoKrFormatError,
    DataGoKrRateLimited,
    DataGoKrUnavailable,
)
from src.ingestion.datagokr.gate import DataGoKrGate
from src.ingestion.datagokr.trade_parse import TradePage, number_trades, parse_trades
from src.ingestion.protocols import AptTrade

from .conftest import FIXTURES, StubResponse, StubSession, load

KEY = "abcdefABCDEF0123456789abcdefABCDEF0123456789abcdefABCDEF01234567"


def load_gz(name: str) -> str:
    return gzip.decompress((FIXTURES / name).read_bytes()).decode("utf-8")


def page(name: str, lawd_cd: str = "11710") -> TradePage:
    body = load_gz(name) if name.endswith(".gz") else load(name)
    ym = name.split("_")[2]
    return parse_trades(body, lawd_cd=lawd_cd, ym=ym)


def month(*names: str) -> tuple[AptTrade, ...]:
    return number_trades(row for name in names for row in page(f"apt/{name}").rows)


def key(t: AptTrade) -> tuple[object, ...]:
    return (t.lawd_cd, t.deal_date, t.apt_seq, t.apt_dong, t.floor, t.excl_area, t.amount)


def first(trades: tuple[AptTrade, ...], **fields: object) -> AptTrade:
    return next(t for t in trades if all(getattr(t, k) == v for k, v in fields.items()))


class Test한_쪽:
    def test_행_수는_totalCount와_같다(self) -> None:
        got = page("apt/trade_11710_202001_p1.xml.gz")
        assert (got.total_count, got.page_no, len(got.rows)) == (213, 1, 213)

    def test_필드를_정규화한다(self) -> None:
        """2020-01 첫 행 — 마천대성 2층 59.62㎡ 7억 5천(2020-01-20)."""
        trade = month("trade_11710_202001_p1.xml.gz")[0]
        assert trade == AptTrade(
            lawd_cd="11710", deal_ym="202001", deal_date=dt.date(2020, 1, 20),
            apt_seq="11710-147", umd_code="1171011400", jibun="574", apt_name="마천대성",
            apt_dong="", floor=2, excl_area=Decimal("59.62"), amount=750_000_000, occurrence=0,
            dealing_type=None, cancelled=False, cancelled_on=None, build_year=1995)

    def test_면적은_받은_자릿수_그대로(self) -> None:
        """소수 4자리(파크하비오 `84.9725`)·3자리(`136.325`)·정수(`99`) — 반올림하지 않는다."""
        jan = month("trade_11710_202001_p1.xml.gz")
        assert first(jan, apt_seq="11710-8245", deal_date=dt.date(2020, 1, 28),
                     floor=16).excl_area == Decimal("84.9725")
        dec = month("trade_11710_200512_p1.xml")
        assert [t.excl_area for t in dec] == [Decimal("99"), Decimal("80.35"), Decimal("136.325")]
        assert all(isinstance(t.excl_area, Decimal) for t in jan)

    def test_금액은_만원_쉼표를_원으로(self) -> None:
        dec = month("trade_11710_200512_p1.xml")
        assert [t.amount for t in dec] == [782_500_000, 515_000_000, 1_140_000_000]
        assert all(type(t.amount) is int for t in dec)

    def test_지번과_법정동_코드(self) -> None:
        dec = month("trade_11710_200512_p1.xml")
        assert [(t.apt_seq, t.umd_code, t.jibun, t.build_year) for t in dec] == [
            ("11710-170", "1171010200", "7", 1979),
            ("11710-159", "1171010100", "101-1", 1981),
            ("11710-89", "1171010800", "150", 1988)]

    def test_해제와_해제_신고일(self) -> None:
        """헬리오시티 2020-06-29 16층 84.99㎡ 17억 8천 — 2020-09-28 해제 신고."""
        june = month("trade_11710_202006_p1.xml.gz", "trade_11710_202006_p2.xml.gz")
        trade = first(june, apt_seq="11710-8865", deal_date=dt.date(2020, 6, 29), floor=16)
        assert (trade.cancelled, trade.cancelled_on) == (True, dt.date(2020, 9, 28))
        assert (trade.excl_area, trade.amount) == (Decimal("84.99"), 1_780_000_000)
        assert sum(t.cancelled for t in june if t.apt_seq == "11710-8865") == 2
        assert all(t.cancelled_on is None for t in june if not t.cancelled)

    def test_거래_유형은_2021_11부터(self) -> None:
        assert {t.dealing_type for t in month("trade_11710_202001_p1.xml.gz")} == {None}
        dec = month("trade_11710_202112_p1.xml.gz")
        assert {t.dealing_type for t in dec} == {"중개거래", "직거래"}
        assert sum(t.dealing_type == "직거래" for t in dec) == 15

    def test_개편_뒤_코드(self) -> None:
        """춘천 새 코드(51110)는 과거 거래를 새 `aptSeq`로 준다. 옛 코드(42110)는 0건(R9-3)."""
        new = page("apt/trade_51110_202001_p1.xml.gz", "51110")
        assert (new.total_count, len(new.rows)) == (308, 308)
        assert {r.apt_seq.split("-")[0] for r in new.rows} == {"51110"}
        old = page("apt/trade_42110_202001_p1.xml", "42110")
        assert (old.total_count, old.rows) == (0, ())


class Test빈_결과:
    @pytest.mark.parametrize("name", ["apt/trade_11710_200511_p1.xml",
                                      "apt/trade_11710_202701_p1.xml"])
    def test_거래가_없는_달은_오류가_아니다(self, name: str) -> None:
        """첫 달 이전(2005-11)·미래 달(2027-01) — 정상 `000` + `<items/>`."""
        got = page(name)
        assert (got.total_count, got.rows) == (0, ())

    def test_첫_달은_2005_12(self) -> None:
        got = page("apt/trade_11710_200512_p1.xml")
        assert (got.total_count, len(got.rows)) == (3, 3)


class Test순번:
    def test_키가_같은_행은_순번으로_가른다(self) -> None:
        """현진타워 2020-02-29 7층 31.02㎡ 2억 8천 — 해제 1건(앞)과 정상 1건(뒤)."""
        feb = month("trade_11710_202002_p1.xml.gz")
        pair = [t for t in feb if (t.apt_seq, t.deal_date, t.floor, t.excl_area, t.amount) == (
            "11710-7775", dt.date(2020, 2, 29), 7, Decimal("31.02"), 280_000_000)]
        assert [(t.occurrence, t.cancelled) for t in pair] == [(0, True), (1, False)]

    def test_순번까지_넣으면_키가_유일하다(self) -> None:
        for names in (("trade_11710_202002_p1.xml.gz",),
                      ("trade_11710_202006_p1.xml.gz", "trade_11710_202006_p2.xml.gz")):
            trades = month(*names)
            assert len({(*key(t), t.occurrence) for t in trades}) == len(trades)

    def test_같은_달을_다시_읽어도_같은_순번(self) -> None:
        once = month("trade_11710_202002_p1.xml.gz")
        again = month("trade_11710_202002_p1.xml.gz")
        assert once == again

    def test_셋이_같으면_0_1_2(self) -> None:
        june = month("trade_11710_202006_p1.xml.gz", "trade_11710_202006_p2.xml.gz")
        group = [t.occurrence for t in june if (t.apt_seq, t.deal_date, t.floor, t.amount) == (
            "11710-6028", dt.date(2020, 6, 15), 28, 2_325_000_000)]
        assert group == [0, 1, 2]

    def test_두_쪽을_건너도_순번이_이어진다(self) -> None:
        """2020-06(1,173건 — 1쪽 1,000행, 2쪽 173행). 올림픽훼밀리타운 6-08 11층 84.705㎡ 14억
        7,700은 쪽마다 하나다."""
        p1 = page("apt/trade_11710_202006_p1.xml.gz")
        p2 = page("apt/trade_11710_202006_p2.xml.gz")
        assert (p1.total_count, len(p1.rows), p2.total_count, len(p2.rows), p2.page_no) == (
            1173, 1000, 1173, 173, 2)
        june = number_trades([*p1.rows, *p2.rows])
        assert len(june) == 1173
        group = [t.occurrence for t in june if (t.apt_seq, t.deal_date, t.floor, t.amount) == (
            "11710-89", dt.date(2020, 6, 8), 11, 1_477_000_000)]
        assert group == [0, 1]


DEC = load("apt/trade_11710_200512_p1.xml")


class Test형식_오류:
    def test_잘린_응답(self) -> None:
        """3건이라면서 2건만 왔다."""
        cut = DEC[:DEC.rindex("<item>")] + DEC[DEC.rindex("</items>"):]
        with pytest.raises(DataGoKrFormatError):
            parse_trades(cut, lawd_cd="11710", ym="200512")

    def test_첫_쪽이_몫보다_적다(self) -> None:
        """1,173건의 1쪽은 1,000행이어야 한다 — 2쪽 몫(173행)만 왔으면 잘림이다."""
        p2 = load_gz("apt/trade_11710_202006_p2.xml.gz")
        with pytest.raises(DataGoKrFormatError):
            parse_trades(p2.replace("<pageNo>2</pageNo>", "<pageNo>1</pageNo>"),
                         lawd_cd="11710", ym="202006")

    @pytest.mark.parametrize(("old", "new"), [
        ("<dealAmount>51,500</dealAmount>", "<dealAmount>오만</dealAmount>"),
        ("<dealAmount>51,500</dealAmount>", "<dealAmount> </dealAmount>"),
        ("<excluUseAr>80.35</excluUseAr>", "<excluUseAr>abc</excluUseAr>"),
        ("<excluUseAr>80.35</excluUseAr>", "<excluUseAr>80.35123</excluUseAr>"),  # 저장 못 함
        ("<excluUseAr>80.35</excluUseAr>", "<excluUseAr>-80.35</excluUseAr>"),
        ("<dealDay>30</dealDay>", "<dealDay>32</dealDay>"),
        ("<floor>7</floor>", "<floor>칠</floor>"),
        ("<aptSeq>11710-159</aptSeq>", "<aptSeq> </aptSeq>"),
        ("<umdCd>10100</umdCd>", "<umdCd>101</umdCd>"),
        ("<cdealType> </cdealType><dealAmount>51,500",
         "<cdealType>O</cdealType><dealAmount>51,500"),  # 해제인데 신고일이 없다
    ])
    def test_읽지_못하는_행이_하나라도_있으면_응답_전체가_형식_오류(self, old: str,
                                                   new: str) -> None:
        assert DEC.count(old) == 1
        with pytest.raises(DataGoKrFormatError):
            parse_trades(DEC.replace(old, new), lawd_cd="11710", ym="200512")

    def test_요청과_다른_시군구나_달의_행(self) -> None:
        with pytest.raises(DataGoKrFormatError):
            parse_trades(DEC, lawd_cd="11720", ym="200512")
        with pytest.raises(DataGoKrFormatError):
            parse_trades(DEC, lawd_cd="11710", ym="200601")

    def test_결과_코드가_000이_아니면_형식_오류(self) -> None:
        bad = DEC.replace("<resultCode>000</resultCode>", "<resultCode>003</resultCode>")
        with pytest.raises(DataGoKrFormatError):
            parse_trades(bad, lawd_cd="11710", ym="200512")

    def test_모양이_다르면_형식_오류(self) -> None:
        with pytest.raises(DataGoKrFormatError):
            parse_trades("<response><header><resultCode>000</resultCode></header></response>",
                         lawd_cd="11710", ym="200512")

    @pytest.mark.parametrize("body", ["Service Unavailable", "<html><body>점검", ""])
    def test_XML이_아니면_연결_오류(self, body: str) -> None:
        with pytest.raises(DataGoKrUnavailable):
            parse_trades(body, lawd_cd="11710", ym="200512")


class Test값의_경계:
    def test_지하층은_음수(self) -> None:
        got = parse_trades(DEC.replace("<floor>7</floor>", "<floor>-1</floor>"),
                           lawd_cd="11710", ym="200512")
        assert got.rows[1].floor == -1

    def test_건축년도가_비면_None(self) -> None:
        got = parse_trades(DEC.replace("<buildYear>1981</buildYear>", "<buildYear> </buildYear>"),
                           lawd_cd="11710", ym="200512")
        assert got.rows[1].build_year is None

    def test_동이_있으면_그대로(self) -> None:
        got = parse_trades(DEC.replace("<aptDong> </aptDong><aptNm>우성",
                                       "<aptDong> 101 </aptDong><aptNm>우성"),
                           lawd_cd="11710", ym="200512")
        assert got.rows[1].apt_dong == "101"


def gateway_client(session: StubSession) -> DataGoKrClient:
    class Counter:
        async def take(self, api: str, day: dt.date, limit: int) -> bool:
            return True

    door = DataGoKrGate(3, Counter(), {"trade": 9000, "region": 9000, "kapt": 4500},
                        today=lambda: dt.date(2026, 10, 5))
    settings = dataclasses.replace(load_settings(), data_api_key=_Secret(KEY),
                                   data_api_retry_max_attempts=3)
    return DataGoKrClient(settings, door, session=session)  # type: ignore[arg-type]


GATEWAY_12 = load("apt/gateway_30.xml").replace("<returnReasonCode>30</returnReasonCode>",
                                                "<returnReasonCode>12</returnReasonCode>")


class Test게이트웨이:
    @pytest.mark.parametrize(("body", "status", "error"), [
        (load("apt/gateway_30.xml"), 403, DataGoKrAuthError),
        (load("apt/gateway_22.xml"), 429, DataGoKrRateLimited),
        (GATEWAY_12, 403, DataGoKrFormatError),
        (load("apt/gateway_30.xml"), 200, DataGoKrAuthError),  # 상태 코드가 200이어도 본문으로
    ])
    async def test_사유별_실패_종류(self, no_sleep: list[float], body: str, status: int,
                             error: type[Exception]) -> None:
        session = StubSession(StubResponse(body, status=status))
        with pytest.raises(error):
            await gateway_client(session).fetch_trades("11710", "200512", 1)
        assert len(session.calls) == 1  # 인증·한도·형식은 다시 시도하지 않는다
