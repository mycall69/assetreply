"""수집 전용 로깅 구성 (T002) — research R3-10.

표준 `logging`에 구조화 포매터를 붙인다. 외부 로깅 라이브러리를 도입하지 않는 이유는
이 기능이 요구하는 것이 구조화된 한 줄과 파일 출력뿐이기 때문이다(헌법 원칙 IX).

**웹서버 표준출력과 분리된 파일에 쓴다.** `be-start.sh`가 이미 표준출력을
`logs/backend.log`로 받고 있어, 수집 로그를 여기 섞으면 접근 로그와 뒤엉켜 운영자가
걸러내야 한다.

비밀값 차단은 여기서 하지 않는다. 이벤트를 만드는 지점에서 애초에 담지 않는다
(FR-020) — 포매터에서 걸러내려면 어떤 필드가 비밀인지 아는 지식이 두 곳에 흩어진다.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

COLLECTION_LOGGER_NAME = "assetreplay.collection"

# `LogRecord`가 기본으로 갖는 속성. 이 목록에 없는 속성만 추가 필드로 싣는다.
_BUILTIN_ATTRS = frozenset({
    "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
    "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
    "pathname", "process", "processName", "relativeCreated", "stack_info",
    "taskName", "thread", "threadName",
})


class StructuredFormatter(logging.Formatter):
    """한 줄 JSON으로 직렬화한다.

    **개행을 반드시 제거한다.** 메시지에 줄바꿈이 섞이면 로그 한 건이 여러 건처럼
    보여, 나중에 사건 수를 세거나 구간을 되짚을 때 숫자가 어긋난다.

    `ensure_ascii=False`인 이유는 이 파일을 사람이 직접 열어 읽기 때문이다. 한글이
    `\\uXXXX`로 이스케이프되면 운영자가 내용을 파악할 수 없다(헌법 원칙 VIII).
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "time": dt.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _BUILTIN_ATTRS and not key.startswith("_"):
                payload[key] = value

        # 직렬화할 수 없는 값이 섞여도 로그 한 줄을 잃지 않는다. 기록은 관찰 수단이라
        # 여기서 예외를 올리면 부가 기능이 본 기능을 멈추게 된다 (FR-018a).
        line = json.dumps(payload, ensure_ascii=False, default=repr)
        return line.replace("\n", " ").replace("\r", " ")


def configure_logging(log_path: str | Path) -> logging.Logger:
    """수집 로거를 구성해 돌려준다. 애플리케이션 기동 시 한 번 호출한다.

    같은 로거를 두 번 구성해도 핸들러가 쌓이지 않는다. 쌓이면 같은 줄이 여러 번
    기록되어 사건 수가 부풀려진다.
    """
    path = Path(log_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(COLLECTION_LOGGER_NAME)
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # `logging.config.fileConfig`가 기본적으로 기존 로거를 끈다. Alembic 등이 먼저
    # 돌았다면 여기서 되살려야 사건이 조용히 사라지지 않는다.
    logger.disabled = False

    # 루트로 전파하지 않는다. 전파하면 웹서버 표준출력에 수집 로그가 섞여
    # 파일을 분리해 둔 의미가 사라진다.
    logger.propagate = False
    return logger


def collection_logger() -> logging.Logger:
    """구성된 수집 로거를 얻는다. 구성 전에 불러도 예외를 내지 않는다."""
    return logging.getLogger(COLLECTION_LOGGER_NAME)
