"""테스트 전역 설정 — **테스트는 개발 DB를 건드리지 않는다.**

## 왜 필요한가

통합 테스트의 `reset_schema()`는 스키마의 모든 테이블을 드롭하고 다시 만든다. 테스트와
개발이 같은 데이터베이스를 쓰면 **수집해 둔 실제 데이터가 통째로 날아간다.**

실제로 일어났다. 개발 DB에 통합 테스트의 스텁(USD 12행, 전부 1200.00, 2020년)만 남아
화면이 2020-12-01을 마지막 확정값으로 표시했다. 화면은 정상 동작했고, 데이터가 잘못이었다.

## 어떻게 막는가

`DB_NAME`에 접미사를 붙여 **별도 데이터베이스**로 보낸다. 환경변수를 바꾸는 이유는
`reset_schema()`가 내부에서 `load_settings()`를 다시 부르기 때문이다 — 픽스처로 설정
객체만 갈아끼우면 그 경로가 여전히 개발 DB를 본다.

모듈 임포트 시점에 적용한다. 픽스처보다 먼저 돌아야 어떤 경로로 `load_settings()`가
불리든 테스트 DB를 가리킨다.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

from src.config.settings import repo_root

#: 테스트 DB 이름에 붙는 접미사. 개발 DB와 한 글자라도 달라야 한다.
TEST_DB_SUFFIX = os.getenv("TEST_DB_SUFFIX", "_test")


def _redirect_to_test_database() -> str:
    """`DB_NAME`을 테스트 전용 이름으로 바꾼다. 바뀐 이름을 돌려준다."""
    # `.env`를 먼저 읽어야 설정된 DB 이름을 알 수 있다. `override=False`라 이미 설정된
    # 환경변수는 그대로 두므로, CI가 DB_NAME을 직접 주는 경우도 그 값을 기준으로 삼는다.
    load_dotenv(repo_root() / ".env", override=False)

    base = os.getenv("DB_NAME", "assetreplay")
    if base.endswith(TEST_DB_SUFFIX):
        return base  # 이미 테스트 DB를 가리키고 있다

    test_name = f"{base}{TEST_DB_SUFFIX}"
    os.environ["DB_NAME"] = test_name
    return test_name


TEST_DB_NAME = _redirect_to_test_database()


def pytest_sessionstart(session: object) -> None:
    """테스트 DB가 없으면 만든다.

    `reset_schema()`는 존재하는 DB에 접속해 테이블을 지우고 다시 만든다. DB 자체가 없으면
    접속 단계에서 실패하므로 여기서 한 번 보장한다.

    원시 SQL을 쓰는 이유: `CREATE DATABASE`는 ORM으로 표현할 수 없고, 접속할 DB가 아직
    없는 상태라 세션도 쓸 수 없다. **테스트 전용 경로**이므로 이식성 제약(헌법 DB 운영
    규약)의 대상이 아니다 — 운영 스키마는 Alembic만 다룬다.
    """
    import pymysql

    user = os.getenv("DB_USER", "")
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "3306")),
            user=user,
            password=os.getenv("DB_PASSWORD", ""),
        )
    except pymysql.Error as exc:
        raise RuntimeError(f"테스트 DB 서버에 접속할 수 없습니다: {exc}") from exc

    try:
        with conn.cursor() as cur:
            cur.execute(
                f"CREATE DATABASE IF NOT EXISTS `{TEST_DB_NAME}` "
                "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    except pymysql.err.OperationalError as exc:
        # 애플리케이션 사용자에게 DB 생성 권한이 없는 것이 정상이다. 권한을 요구하는
        # 대신, 관리자가 한 번 해 줄 일을 정확히 알려준다.
        raise RuntimeError(
            f"테스트 DB `{TEST_DB_NAME}`를 만들 수 없습니다 ({exc}).\n"
            f"관리자 계정으로 아래를 한 번 실행하세요.\n\n"
            f"  CREATE DATABASE `{TEST_DB_NAME}` "
            f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;\n"
            f"  GRANT ALL PRIVILEGES ON `{TEST_DB_NAME}`.* TO '{user}'@'localhost';\n"
            f"  FLUSH PRIVILEGES;\n\n"
            f"테스트는 개발 DB를 드롭·재생성하므로 분리가 필요합니다."
        ) from exc
    finally:
        conn.close()
