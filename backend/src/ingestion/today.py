"""오늘 하루치 조회와 잠정 저장 (T065).

**이 모듈은 커버리지를 갱신하지 않는다.** 그것이 이 파일이 `collector.py`와 분리되어
존재하는 이유다 (FR-037b, research R2-2).

잠정 저장이 `fx_coverage.covered_through`를 오늘까지 밀면, 001의 재개 로직이 다음
증분 수집에서 오늘을 건너뛴다. 그러면 잠정값이 영원히 확정값으로 대체되지 않고,
화면은 계속 "잠정"으로 남으며 출처가 정정해도 반영되지 않는다. 오류는 나지 않으므로
며칠 뒤에야 드러난다.

`tests/unit/test_today_isolation.py`가 이 경계를 정적으로 검사한다.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dialect import upsert
from src.db.models import FxRate, FxRawResponse
from src.ingestion.protocols import DailyQuote, FetchOutcome, FxRateSource

SOURCE_ID = "ECOS:731Y001"


async def store_provisional(
    session: AsyncSession,
    currency_code: str,
    quote: DailyQuote,
    *,
    today: dt.date,
    source: str = SOURCE_ID,
) -> None:
    """오늘 값을 잠정으로 저장한다 (FR-037, FR-037c).

    같은 날 여러 번 새로고침하면 값만 갱신되고 잠정 상태는 유지된다. 확정 전환은
    날짜가 지난 뒤 증분 수집이 그 날짜를 다시 받아올 때만 일어난다 (FR-037a).

    **오늘이 아닌 날짜는 잠정으로 저장할 수 없다** (FR-037c). 과거에 잠정 레코드가
    생기면 "확정 전환이 안 일어난 것"과 구별되지 않는다. 두 원인이 같은 증상을 내면
    원인을 좁힐 수 없으므로, 애초에 만들지 못하게 막는다.

    날짜를 오늘로 제한하면 "통화당 최대 하나"는 기본 키 `(currency_code, quote_date)`에서
    자동으로 따라온다 — 오늘은 하루뿐이므로 행도 하나뿐이다.

    `today`를 인자로 받는 이유는 호출 시점의 날짜를 호출자가 정하기 때문이다. 내부에서
    `date.today()`를 부르면 자정 경계에서 조회와 저장이 다른 날을 가리킬 수 있다.
    """
    if quote.quote_date != today:
        raise ValueError(
            f"잠정 저장은 오늘({today})만 허용됩니다: {quote.quote_date} (FR-037c)")

    await upsert(session, FxRate, [{
        "currency_code": currency_code,
        "quote_date": quote.quote_date,
        "base_rate": quote.base_rate,
        "quote_unit": quote.quote_unit,
        "source": source,
        "is_provisional": True,
    }])


async def fetch_today(
    session: AsyncSession, src: FxRateSource, currency_code: str, today: dt.date
) -> FxRate | None:
    """오늘 하루치만 받아와 잠정으로 저장한다 (FR-036).

    과거 구간을 다시 요청하지 않는다. 반환값이 `None`이면 오늘 고시가 아직 없다는
    뜻이며, 값을 만들어내거나 인접일 값으로 대체하지 않는다 (FR-039).
    """
    result = await src.fetch_daily_rates(currency_code, today, today)

    # 원본 응답은 성공·실패와 무관하게 남긴다. 잠정→확정 전환 시 값 변화를 대조하는
    # 근거가 된다 (FR-043, research R2-3).
    session.add(FxRawResponse(
        currency_code=currency_code,
        requested_from=today,
        requested_to=today,
        http_status=result.raw_status,
        result_code=result.raw_result_code,
        body=result.raw_body,
    ))

    if result.outcome is not FetchOutcome.OK or not result.quotes:
        await session.commit()
        return None

    quote = result.quotes[0]
    await store_provisional(session, currency_code, quote, today=today)
    await session.commit()

    return (await session.get(FxRate, (currency_code, today)))
