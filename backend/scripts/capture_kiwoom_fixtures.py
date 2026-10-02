"""키움 REST API 응답을 계약 테스트 픽스처로 저장한다 (006 T004).

**테스트 스위트에서 실행되지 않는다.** 실제 출처를 부르고 인증 정보가 필요하다. 개발자가
한 번 손으로 돌려 `tests/contract/fixtures/kiwoom/`를 만든다(T005).

저장하지 않는 것 (006 FR-061):

- **토큰 발급 응답** — 접근 토큰이 들어 있다
- **요청·응답 헤더** — `authorization`이 섞인다. 연속조회에 필요한 `cont-yn`·`next-key`만
  메타 파일에 따로 남긴다(커서라 비밀이 아니다)

키·시크릿·토큰은 화면에도 찍지 않는다.

사용법::

    cd backend
    .venv/bin/python scripts/capture_kiwoom_fixtures.py --pages 2
    .venv/bin/python scripts/capture_kiwoom_fixtures.py --units NYSE --pages 0   # 전 쪽 측정
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from src.config.settings import load_settings  # noqa: E402

DOMAINS = {"real": "https://api.kiwoom.com", "mock": "https://mockapi.kiwoom.com"}

#: 단위 → (api-id, 경로, 요청 본문). research R6-2의 단위 표.
UNITS: dict[str, tuple[str, str, dict[str, str]]] = {
    "KOSPI": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "0"}),
    "KOSDAQ": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "10"}),
    "KR_ETF": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "8"}),
    "KR_REIT": ("ka10099", "/api/dostk/stkinfo", {"mrkt_tp": "6"}),
    "NYSE": ("usa10099", "/api/us/stkinfo", {"stex_tp": "NY"}),
    "NASDAQ": ("usa10099", "/api/us/stkinfo", {"stex_tp": "ND"}),
    "AMEX": ("usa10099", "/api/us/stkinfo", {"stex_tp": "NA"}),
}
US_UNITS = {"NYSE", "NASDAQ", "AMEX"}


@dataclass
class UnitReport:
    unit: str
    pages: int = 0
    rows_per_page: list[int] = field(default_factory=list)
    complete: bool = False
    error: str | None = None
    #: 클래스 주식처럼 기호가 섞인 티커. 표기 규칙(research R6-6)을 정하는 근거다.
    symbol_samples: list[str] = field(default_factory=list)


def _code_of(row: dict[str, object]) -> str:
    return str(row.get("stk_cd") or row.get("code") or "")


async def fetch_token(http: aiohttp.ClientSession, base: str, key: str, secret: str) -> str:
    async with http.post(
        f"{base}/oauth2/token",
        json={"grant_type": "client_credentials", "appkey": key, "secretkey": secret},
        headers={"Content-Type": "application/json;charset=UTF-8"},
    ) as res:
        body = await res.json(content_type=None)
    code = body.get("return_code")
    if code not in (None, 0) or not body.get("token"):
        # 메시지만 보인다 — 본문에 토큰이 섞였을 수 있어 통째로 찍지 않는다.
        raise SystemExit(f"토큰 발급 실패: return_code={code} {body.get('return_msg')!r}")
    return str(body["token"])


async def capture_unit(
    http: aiohttp.ClientSession, base: str, token: str, unit: str,
    out: Path, max_pages: int, delay: float, save_pages: int,
) -> UnitReport:
    api_id, path, payload = UNITS[unit]
    report = UnitReport(unit)
    cont_yn, next_key = "N", ""
    page = 0
    while True:
        page += 1
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "api-id": api_id,
            "authorization": f"Bearer {token}",
        }
        if page > 1:
            headers["cont-yn"] = cont_yn
            headers["next-key"] = next_key
        async with http.post(f"{base}{path}", json=payload, headers=headers) as res:
            status = res.status
            text = await res.text()
            cont_yn = res.headers.get("cont-yn") or res.headers.get("Cont-Yn") or "N"
            next_key = res.headers.get("next-key") or res.headers.get("Next-Key") or ""

        try:
            body = json.loads(text)
        except json.JSONDecodeError:
            report.error = f"쪽 {page}: JSON이 아님 (HTTP {status})"
            return report
        code = body.get("return_code")
        rows = body.get("list") or []
        report.pages = page
        report.rows_per_page.append(len(rows))
        for row in rows:
            symbol = _code_of(row)
            if unit in US_UNITS and any(ch in symbol for ch in "./- ") and len(report.symbol_samples) < 10:
                report.symbol_samples.append(symbol)

        if page <= save_pages or (report.symbol_samples and not (out / f"{unit}_class.json").exists()
                                  and any(any(ch in _code_of(r) for ch in "./- ") for r in rows)):
            name = f"{unit}_p{page:02d}.json" if page <= save_pages else f"{unit}_class.json"
            (out / name).write_text(text, encoding="utf-8")
            (out / (name.removesuffix(".json") + ".meta.json")).write_text(json.dumps(
                {"status": status, "cont_yn": cont_yn, "next_key": next_key,
                 "return_code": code, "page": page}, ensure_ascii=False, indent=1),
                encoding="utf-8")

        if code not in (None, 0):
            report.error = f"쪽 {page}: return_code={code} {body.get('return_msg')!r}"
            return report
        if cont_yn != "Y" or (max_pages and page >= max_pages):
            report.complete = cont_yn != "Y"
            return report
        await asyncio.sleep(delay)


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--units", default=",".join(UNITS), help="쉼표로 구분한 단위")
    parser.add_argument("--pages", type=int, default=2, help="받을 최대 쪽 수(0이면 끝까지)")
    parser.add_argument("--save", type=int, default=2, help="앞에서부터 저장할 쪽 수")
    parser.add_argument("--out", default=str(BACKEND / "tests/contract/fixtures/kiwoom"))
    args = parser.parse_args()

    settings = load_settings()
    if not settings.kiwoom_credentials_present:
        raise SystemExit("키움 인증 정보가 없습니다 — 저장소 루트 .env의 KIWOOM_APP_KEY·KIWOOM_APP_SECRET")
    base = DOMAINS[settings.kiwoom_mode]
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as http:
        token = await fetch_token(
            http, base, settings.kiwoom_app_key.reveal(), settings.kiwoom_app_secret.reveal())
        print(f"모드 {settings.kiwoom_mode} — 토큰 발급 성공(값은 출력하지 않음)")
        for unit in [u.strip() for u in args.units.split(",") if u.strip()]:
            delay = (settings.kiwoom_us_page_delay_seconds if unit in US_UNITS
                     else settings.kiwoom_kr_page_delay_seconds)
            started = time.monotonic()
            r = await capture_unit(http, base, token, unit, out, args.pages, delay, args.save)
            took = time.monotonic() - started
            print(json.dumps({
                "unit": r.unit, "pages": r.pages, "rows_per_page": r.rows_per_page[:5],
                "total_rows_seen": sum(r.rows_per_page), "complete": r.complete,
                "seconds": round(took, 1), "error": r.error,
                "symbol_samples": r.symbol_samples,
            }, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
