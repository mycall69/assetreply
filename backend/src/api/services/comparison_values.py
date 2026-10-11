"""비교 수익률 추이의 현재 가치 — 일시금의 날짜별 원화 총자산 (014 반복 2026-10-11b).

spec FR-036, contracts A12, data-model 14, research R14-29.

주식·가상자산 일시금의 시계열 점 `balance`는 **보유분만의 원화 평가**다(예수금·매수 뒤 남은
현금이 빠진다). 비교 표의 "현재 가치"(요약 `totalKrw`)는 원화 원금 + 투자 수익이라, 점마다 같은
뜻의 값을 그 계산의 행에서 고른다 — 새로 계산하지 않는다. 투자 수익은 `fx_convert.evaluate_krw`가
이미 낸 (잔고 + 예수금) × 그 행의 매매기준율 − 원화 원금이다. 요약의 `totalKrw`와 같은 식(투자
수익 + 원화 원금)이라 기준일 점은 그 글자와 같다.

적립식·정기예금·적금·부동산은 점 `balance`가 곧 원화 총자산이라 이 모듈을 거치지 않는다
(`comparison_metrics.value_points`).
"""

from __future__ import annotations

from decimal import Decimal

from src.api.services.crypto_simulation import CryptoResult
from src.api.services.stock_simulation import SimulationResult


def _basis(principal_krw: Decimal | None, principal: Decimal) -> Decimal:
    """원화 원금 — 원금 통화가 원화가 아니면 첫 매수일 매매기준율로 평가한 원금이다."""
    return principal_krw if principal_krw is not None else principal


def stock_lump_totals(result: SimulationResult, principal: Decimal) -> dict[str, str]:
    """날짜 글자 → 그 날 **마지막 행**의 원화 총자산.

    시계열(`stock_series._one_per_day`)과 같은 차례로 같은 행을 고른다 — 배당락 날처럼 한 날에 행이
    둘이면 나중 것이 그 날의 최종 상태다.
    """
    basis = _basis(result.principal_krw, principal)
    totals: dict[str, str] = {}
    for converted in sorted(result.rows, key=lambda c: c.row.date):
        totals[converted.row.date.isoformat()] = format(converted.row.profit + basis, "f")
    return totals


def crypto_lump_totals(result: CryptoResult, principal: Decimal) -> dict[str, str]:
    """날짜 글자 → 그 일봉의 원화 총자산. 시계열 점은 일봉마다다(`crypto_series` — `daily`)."""
    basis = _basis(result.principal_krw, principal)
    return {view.row.date.isoformat(): format(view.profit + basis, "f")
            for view in result.daily}
