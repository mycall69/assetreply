"""단지 짝짓기 (T014) — 009 FR-003, FR-032, research R9-3.

단지 목록 자료(`kaptCode`)와 실거래(`aptSeq`)의 같은 단지를 한 행으로 만든다. 법정동 코드가 같고
다음 중 하나면 같은 단지다:

1. 지번 본번·부번이 같다(실거래 `jibun`, 목록은 기본 정보의 `kaptAddr`에서 뽑은 본번·부번) 2.
정규화한 이름(공백·괄호와 그 안·"아파트" 제거)이 같고 그 이름이 그 동의 **두 자료에서 하나씩뿐**이다

헬리오시티는 대표 지번이 자료마다 다르다(단지 목록 479, 실거래 913 — T001 실측) — 지번만으로
짝지으면 두 번 보인다. 같은 동에 같은 이름이 여럿이면 이름으로 짝짓지 않는다 — 다른 단지를 하나로
합치는 것보다 따로 보이는 편이 덜 위험하다. 단지 행은 지우지 않는다 — 두 행이 이미 따로 있을 때 짝이
드러나면 먼저 만든 행(작은 id)에 합치고 다른 행은 `merged_into`다(이력이 단지 id를 저장한다,
FR-032).
"""
from __future__ import annotations

import datetime as dt
import gzip
from pathlib import Path

from src.api.services.realestate_complex_match import (
    ComplexIds,
    KaptSide,
    TradeSide,
    jibun_key,
    match_complexes,
    normalize_name,
    plan_merges,
    trade_sides,
)
from src.ingestion.datagokr.kapt_parse import parse_complex_basis, parse_complex_list
from src.ingestion.datagokr.trade_parse import number_trades, parse_trades

FIXTURES = Path(__file__).resolve().parents[1] / "contract" / "fixtures" / "apt"
GARAK = "1171010700"


def garak_kapt() -> list[KaptSide]:
    listing = parse_complex_list((FIXTURES / "kapt_list_1171010700.json").read_text("utf-8"))
    sides = []
    for item in listing.complexes:
        basis = parse_complex_basis(
            (FIXTURES / f"kapt_basis_{item.kapt_code}.json").read_text("utf-8"))
        jibun = None
        if basis is not None and basis.bonbun is not None:
            jibun = f"{basis.bonbun}" + (f"-{basis.bubun}" if basis.bubun else "")
        sides.append(KaptSide(item.kapt_code, item.name, item.bjd_code, jibun))
    return sides


def garak_trades() -> tuple[TradeSide, ...]:
    trades = []
    for path in sorted(FIXTURES.glob("trade_11710_20*.xml.gz")):
        page = parse_trades(gzip.decompress(path.read_bytes()).decode("utf-8"),
                            lawd_cd="11710", ym=path.name.split("_")[2])
        trades.extend(t for t in number_trades(page.rows) if t.umd_code == GARAK)
    return trade_sides(trades)


class Test이름_정규화:
    def test_공백_괄호_아파트를_지운다(self) -> None:
        assert normalize_name("헬리오시티아파트") == "헬리오시티"
        assert normalize_name("가락3차쌍용스윗닷홈(1~4동)") == "가락3차쌍용스윗닷홈"
        assert normalize_name("가락(1차)쌍용아파트") == "가락쌍용"
        assert normalize_name(" 송파 Nsuite ") == "송파Nsuite"

    def test_지번_키(self) -> None:
        assert jibun_key("913") == (913, 0)
        assert jibun_key("101-1") == (101, 1)
        assert jibun_key("142-") == (142, 0)  # 단지 기본 정보 주소의 부번 없는 꼴
        assert jibun_key("산12") is None
        assert jibun_key("") is None


class Test가락동_픽스처:
    def test_실거래_단지는_aptSeq마다_하나_최근_이름(self) -> None:
        sides = garak_trades()
        assert len(sides) == 78
        assert len({s.apt_seq for s in sides}) == 78
        helio = next(s for s in sides if s.apt_seq == "11710-8865")
        assert (helio.name, helio.umd_code, helio.jibun, helio.build_year) == (
            "헬리오시티", GARAK, "913", 2018)

    def test_짝짓기_성공과_실패_수(self) -> None:
        matching = match_complexes(garak_kapt(), garak_trades())
        assert len(matching.pairs) == 22
        # 더샵송파루미스타 — 2026 입주, 받은 범위에 거래가 없다
        assert matching.kapt_only == ("A10020074",)
        assert len(matching.trade_only) == 56

    def test_헬리오시티는_지번이_달라도_이름으로_한_단지(self) -> None:
        pairs = dict(match_complexes(garak_kapt(), garak_trades()).pairs)
        assert pairs["A10025850"] == "11710-8865"

    def test_지번이_같으면_이름이_달라도_한_단지(self) -> None:
        """가락풍림아파트(142) ↔ 풍림1(142), 송파롯데캐슬파인힐(79) ↔ 롯데캐슬(79)."""
        pairs = dict(match_complexes(garak_kapt(), garak_trades()).pairs)
        assert (pairs["A10021256"], pairs["A13816005"]) == ("11710-65", "11710-200")

    def test_한_단지가_두_번_나오지_않는다(self) -> None:
        """가락3차쌍용스윗닷홈은 실거래가 동마다 다른 aptSeq다 — 지번이 같은 하나(52)와만
        짝짓는다."""
        matching = match_complexes(garak_kapt(), garak_trades())
        kapt_codes = [k for k, _ in matching.pairs] + list(matching.kapt_only)
        apt_seqs = [s for _, s in matching.pairs] + list(matching.trade_only)
        assert len(kapt_codes) == len(set(kapt_codes)) == 23
        assert len(apt_seqs) == len(set(apt_seqs)) == 78
        assert dict(matching.pairs)["A13895502"] == "11710-232"


def side(seq: str, name: str, jibun: str, umd: str = GARAK) -> TradeSide:
    return TradeSide(seq, name, umd, jibun, None)


class Test규칙:
    def test_같은_동_같은_이름_다른_지번이면_짝짓지_않는다(self) -> None:
        kapt = [KaptSide("A1", "현대", GARAK, "10"), KaptSide("A2", "현대", GARAK, "20")]
        trade = [side("S1", "현대", "11"), side("S2", "현대아파트", "21")]
        matching = match_complexes(kapt, trade)
        assert matching.pairs == ()
        assert (matching.kapt_only, matching.trade_only) == (("A1", "A2"), ("S1", "S2"))

    def test_이름이_한쪽에만_하나여도_짝짓지_않는다(self) -> None:
        """목록에는 하나지만 실거래에는 둘 — 어느 쪽인지 모른다."""
        kapt = [KaptSide("A1", "동성", GARAK, None)]
        trade = [side("S1", "동성아파트(101동)", "15"), side("S2", "동성아파트(102동)", "15-4")]
        assert match_complexes(kapt, trade).pairs == ()

    def test_다른_동은_짝짓지_않는다(self) -> None:
        kapt = [KaptSide("A1", "헬리오시티", GARAK, "913")]
        trade = [side("S1", "헬리오시티", "913", umd="1171010800")]
        assert match_complexes(kapt, trade).pairs == ()

    def test_지번을_아직_모르면_이름으로만(self) -> None:
        kapt = [KaptSide("A1", "가락미륭아파트", GARAK, None)]
        trade = [side("S1", "가락미륭", "138")]
        assert match_complexes(kapt, trade).pairs == (("A1", "S1"),)

    def test_이미_짝지은_것은_그대로_두고_세는_데만_쓴다(self) -> None:
        """이미 한 행인 짝(fixed)은 다시 짝짓지 않는다. 이름의 유일성은 그 짝까지 세어 판정한다."""
        kapt = [KaptSide("A1", "현대", GARAK, "10"), KaptSide("A2", "현대", GARAK, None)]
        trade = [side("S1", "현대", "10"), side("S2", "현대", "30")]
        matching = match_complexes(kapt, trade, fixed=[("A1", "S1")])
        assert matching.pairs == (("A1", "S1"),)
        assert (matching.kapt_only, matching.trade_only) == (("A2",), ("S2",))

    def test_이름이_바뀐_단지는_최근_이름(self) -> None:
        class T:
            def __init__(self, day: str, name: str) -> None:
                self.apt_seq, self.apt_name, self.umd_code, self.jibun = "S1", name, GARAK, "1"
                self.deal_date, self.build_year = dt.date.fromisoformat(day), 1990

        sides = trade_sides([T("2021-05-01", "새이름"), T("2019-01-01", "옛이름")])
        assert [(s.apt_seq, s.name) for s in sides] == [("S1", "새이름")]


GAEPO = "1168010300"


class Test재건축:
    """같은 필지의 재건축 전 옛 단지와 새 단지는 짝짓지 않는다(T027 실측 — 개포동 개포주공4단지 ↔
    개포자이프레지던스). 재건축 전후 연결은 범위 밖이다. 건축년도와 사용승인 연도를 둘 다 알고 10년
    넘게 다를 때만 막는다."""

    def test_지번이_같아도_연도가_10년_넘게_다르면_짝짓지_않는다(self) -> None:
        kapt = [KaptSide("A1", "개포자이프레지던스", GAEPO, "189", move_in_year=2023)]
        trade = [TradeSide("11680-289", "개포주공4단지", GAEPO, "189", 1982),
                 TradeSide("11680-5235", "개포자이프레지던스", GAEPO, "1284", 2023)]
        matching = match_complexes(kapt, trade)
        assert matching.pairs == (("A1", "11680-5235"),)  # 새 단지와는 이름으로
        assert matching.trade_only == ("11680-289",)

    def test_이름이_같아도_연도가_10년_넘게_다르면_짝짓지_않는다(self) -> None:
        kapt = [KaptSide("A1", "현대", GAEPO, None, move_in_year=2020)]
        trade = [TradeSide("S1", "현대", GAEPO, "5", 1980)]
        assert match_complexes(kapt, trade).pairs == ()

    def test_10년_안의_차이는_짝짓는다(self) -> None:
        """가락현대5차 — 사용승인 1986, 실거래 건축년도 1989(픽스처 실측)."""
        kapt = [KaptSide("A1", "가락현대5차", GARAK, "161-2", move_in_year=1986)]
        trade = [TradeSide("11710-71", "현대(5차)", GARAK, "161-2", 1989)]
        assert match_complexes(kapt, trade).pairs == (("A1", "11710-71"),)

    def test_한쪽_연도를_모르면_보지_않는다(self) -> None:
        kapt = [KaptSide("A1", "새단지", GAEPO, "189")]
        trade = [TradeSide("S1", "옛단지", GAEPO, "189", 1982)]
        assert match_complexes(kapt, trade).pairs == (("A1", "S1"),)


class Test합치기:
    def test_따로_있는_두_행은_작은_id에_합친다(self) -> None:
        rows = [ComplexIds(5, "A1", None), ComplexIds(9, None, "S1"), ComplexIds(3, None, "S2")]
        merges = plan_merges(rows, [("A1", "S1"), ("A9", "S2")])
        assert merges == ((5, 9),)  # A9는 행이 없다 — 합칠 것이 없다

    def test_먼저_만든_행이_실거래_쪽이면_그쪽에(self) -> None:
        rows = [ComplexIds(12, "A1", None), ComplexIds(4, None, "S1")]
        assert plan_merges(rows, [("A1", "S1")]) == ((4, 12),)

    def test_이미_한_행이면_합칠_것이_없다(self) -> None:
        rows = [ComplexIds(7, "A1", "S1")]
        assert plan_merges(rows, [("A1", "S1")]) == ()
