"""주식 매도 세금 설정 저장소 (011 T005) — FR-035, FR-037, data-model 1.1, research R11-7.

`stock_setting`의 열 셋(국내 매도 세율·해외 양도소득세율·해외 기본공제)은 **NULL = 기본값**이다.

- 기본값은 010 반복 4의 법령 표 값과 **문자열까지** 같다(`"0.0020"`·`"0.22"`·`"2500000"`). 그래야
  기본 설정의 보드 응답이 바뀌지 않는다
- 수수료·배당 세율만 저장한 기존 행은 그대로 읽히고, 매도 세금은 기본값이다
- 기존 `get_settings`·`save_settings`의 결과는 바뀌지 않는다
"""

from __future__ import annotations

from decimal import Decimal

from src.repository.stock_setting import (
    DEFAULT_CAPITAL_GAINS_DEDUCTION,
    DEFAULT_CAPITAL_GAINS_RATE,
    DEFAULT_SALE_TAX_DOMESTIC,
    get_sale_tax,
    get_settings,
    save_sale_tax,
    save_settings,
)

M = Decimal


async def test_행이_없으면_기본값이고_문자열이_010_표_값과_같다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        got = await get_sale_tax(s)
    assert (str(got.domestic), str(got.foreign_rate), str(got.foreign_deduction)) == (
        "0.0020", "0.22", "2500000")
    assert got.is_default is True
    defaults = (DEFAULT_SALE_TAX_DOMESTIC, DEFAULT_CAPITAL_GAINS_RATE,
                DEFAULT_CAPITAL_GAINS_DEDUCTION)
    assert defaults == (M("0.0020"), M("0.22"), M("2500000"))


async def test_수수료만_저장한_기존_행은_매도_세금이_기본값이다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await save_settings(s, trade_fee_rate=M("0.000300"), dividend_tax_rate_domestic=M("0.154"),
                            dividend_tax_rate_foreign=M("0.15"))
        await s.commit()
    async with session_factory() as s:
        got = await get_sale_tax(s)
        settings = await get_settings(s)
    texts = (str(got.domestic), str(got.foreign_rate), str(got.foreign_deduction))
    assert texts == ("0.0020", "0.22", "2500000") and got.is_default is True
    assert settings.trade_fee_rate == M("0.000300")


async def test_저장하면_DB_자릿수로_돌아오고_기본값이_아니다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await save_sale_tax(s, domestic=M("0.0015"), foreign_rate=M("0.20"),
                            foreign_deduction=M("0"))
        await s.commit()
    async with session_factory() as s:
        got = await get_sale_tax(s)
    assert (str(got.domestic), str(got.foreign_rate), str(got.foreign_deduction)) == (
        "0.001500", "0.200000", "0")
    assert got.is_default is False


async def test_매도_세금을_저장해도_수수료_배당_세율은_그대로다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await save_settings(s, trade_fee_rate=M("0.000300"), dividend_tax_rate_domestic=M("0.10"),
                            dividend_tax_rate_foreign=M("0.12"))
        await s.commit()
        await save_sale_tax(s, domestic=M("0.0018"), foreign_rate=M("0.22"),
                            foreign_deduction=M("2500000"))
        await s.commit()
    async with session_factory() as s:
        settings = await get_settings(s)
        got = await get_sale_tax(s)
    assert (settings.trade_fee_rate, settings.dividend_tax_rate_domestic,
            settings.dividend_tax_rate_foreign) == (M("0.000300"), M("0.10"), M("0.12"))
    assert got.domestic == M("0.0018") and got.is_default is False


async def test_수수료를_다시_저장해도_매도_세금은_그대로다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await save_sale_tax(s, domestic=M("0.0015"), foreign_rate=M("0.22"),
                            foreign_deduction=M("2500000"))
        await s.commit()
        await save_settings(s, trade_fee_rate=M("0.000150"), dividend_tax_rate_domestic=M("0.154"),
                            dividend_tax_rate_foreign=M("0.15"))
        await s.commit()
    async with session_factory() as s:
        got = await get_sale_tax(s)
    assert got.domestic == M("0.0015")


async def test_기본값과_같은_값을_저장하면_기본값이다(session_factory) -> None:  # type: ignore[no-untyped-def]
    async with session_factory() as s:
        await save_sale_tax(s, domestic=M("0.002"), foreign_rate=M("0.22"),
                            foreign_deduction=M("2500000"))
        await s.commit()
    async with session_factory() as s:
        assert (await get_sale_tax(s)).is_default is True
