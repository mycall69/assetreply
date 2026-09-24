"""수집 로깅 구성 검증 (T004).

두 가지를 본다.

1. 포매터가 **개행 없는 한 줄**을 만든다. 여러 줄이 되면 로그 한 건이 여러 건처럼
   보여 사후 집계가 어긋난다.
2. 수집 로거가 **루트 핸들러로 전파되지 않는다**. 전파되면 웹서버 표준출력
   (`logs/backend.log`)에 수집 로그가 섞여, 분리해 둔 의미가 사라진다 (R3-10).
"""
from __future__ import annotations

import json
import logging

from src.observability.logging_config import (
    COLLECTION_LOGGER_NAME,
    StructuredFormatter,
    configure_logging,
)


def _record(msg: str, **extra: object) -> logging.LogRecord:
    r = logging.LogRecord(
        name=COLLECTION_LOGGER_NAME, level=logging.INFO, pathname=__file__,
        lineno=1, msg=msg, args=(), exc_info=None,
    )
    for k, v in extra.items():
        setattr(r, k, v)
    return r


class Test포매터:
    def test_한_줄로_직렬화한다(self) -> None:
        out = StructuredFormatter().format(_record("첫째 줄\n둘째 줄"))
        assert "\n" not in out

    def test_JSON으로_파싱된다(self) -> None:
        out = StructuredFormatter().format(_record("구간 저장"))
        parsed = json.loads(out)
        assert parsed["message"] == "구간 저장"
        assert parsed["level"] == "INFO"
        assert "time" in parsed

    def test_한글이_이스케이프되지_않는다(self) -> None:
        """`ensure_ascii=True`면 사람이 파일을 열어 읽을 수 없다."""
        out = StructuredFormatter().format(_record("고시 없음"))
        assert "고시 없음" in out

    def test_추가_필드가_실린다(self) -> None:
        out = StructuredFormatter().format(
            _record("구간 저장", currency="USD", rows_stored=261))
        parsed = json.loads(out)
        assert parsed["currency"] == "USD"
        assert parsed["rows_stored"] == 261

    def test_직렬화_불가_값도_한_줄을_깨뜨리지_않는다(self) -> None:
        out = StructuredFormatter().format(_record("x", weird=object()))
        assert "\n" not in out
        json.loads(out)


class Test로거_구성:
    def test_루트로_전파되지_않는다(self, tmp_path) -> None:
        configure_logging(tmp_path / "collection.log")
        assert logging.getLogger(COLLECTION_LOGGER_NAME).propagate is False

    def test_지정한_파일에_쓴다(self, tmp_path) -> None:
        target = tmp_path / "collection.log"
        configure_logging(target)
        logging.getLogger(COLLECTION_LOGGER_NAME).info("수집 시작")
        logging.shutdown()
        assert target.exists()
        assert "수집 시작" in target.read_text(encoding="utf-8")

    def test_부모_디렉터리가_없어도_만든다(self, tmp_path) -> None:
        target = tmp_path / "깊은" / "경로" / "collection.log"
        configure_logging(target)
        logging.getLogger(COLLECTION_LOGGER_NAME).info("생성 확인")
        logging.shutdown()
        assert target.exists()

    def test_두_번_불러도_핸들러가_중복되지_않는다(self, tmp_path) -> None:
        """재구성이 핸들러를 쌓으면 같은 줄이 여러 번 기록된다."""
        configure_logging(tmp_path / "a.log")
        configure_logging(tmp_path / "b.log")
        assert len(logging.getLogger(COLLECTION_LOGGER_NAME).handlers) == 1


class Test로그_경로_해석:
    """상대 경로는 저장소 루트 기준으로 푼다.

    uvicorn이 `backend/`에서 뜨므로 그대로 두면 `backend/logs/`에 생겨,
    `be-start.sh`가 쓰는 루트 `logs/`와 갈라진다. 운영자가 두 곳을 뒤져야 한다.
    """

    def test_상대_경로는_저장소_루트_기준이다(self) -> None:
        from src.config.settings import load_settings, repo_root

        path = load_settings().collection_log_file()
        assert path.is_absolute()
        assert path.parent.parent == repo_root()

    def test_절대_경로는_그대로_쓴다(self, monkeypatch, tmp_path) -> None:
        from src.config.settings import load_settings

        target = tmp_path / "collection.log"
        monkeypatch.setenv("COLLECTION_LOG_PATH", str(target))
        assert load_settings().collection_log_file() == target

    def test_기본값이_backend_아래가_아니다(self) -> None:
        from src.config.settings import load_settings

        assert "backend" not in load_settings().collection_log_file().parts
