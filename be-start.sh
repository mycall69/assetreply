#!/usr/bin/env bash
# 백엔드(FastAPI/uvicorn) 시작. 이미 실행 중이면 먼저 종료하고 재시작한다.
#
# 종료 로직은 be-stop.sh 하나에만 둔다. 여기서 다시 구현하면 두 곳이 어긋난다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${BE_PORT:-8080}"
PYTHON="$ROOT/backend/.venv/bin/python"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/backend.log"
PID_FILE="$LOG_DIR/backend.pid"

# ── 사전 점검: 없으면 무엇을 해야 하는지 알려주고 멈춘다 ──
if [[ ! -x "$PYTHON" ]]; then
  echo "오류: 가상환경을 찾을 수 없습니다 → $PYTHON" >&2
  echo "  헌법 'Python 가상환경 [필수]'에 따라 .venv 안에서 실행해야 합니다." >&2
  echo "  생성: cd backend && python3.14 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
fi

if [[ ! -f "$ROOT/.env" ]]; then
  echo "오류: 저장소 루트에 .env가 없습니다 → $ROOT/.env" >&2
  echo "  .env.example을 복사해 ECOS_API_KEY와 DB 접속 정보를 채우세요." >&2
  exit 1
fi

# ── 실행 중이면 종료 (요구사항: 돌고 있으면 스탑 후 재시작) ──
"$ROOT/be-stop.sh"

mkdir -p "$LOG_DIR"

# uvicorn은 cwd 기준으로 `src.api.main`을 임포트하므로 backend/에서 띄운다.
echo "백엔드 시작 중… (포트 $PORT)"
cd "$ROOT/backend"
nohup "$PYTHON" -m uvicorn src.api.main:app --reload --port "$PORT" \
  >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

# ── 기동 확인: /health가 응답할 때까지 최대 30초 대기 ──
# 여기서 기다리지 않으면 즉시 죽은 경우에도 "시작됨"이라고 보고하게 된다.
for _ in $(seq 1 60); do
  if curl -fsS "http://localhost:$PORT/health" >/dev/null 2>&1; then
    echo "백엔드 준비 완료 → http://localhost:$PORT (PID $(cat "$PID_FILE"))"
    echo "  로그: $LOG_FILE"
    exit 0
  fi
  # 프로세스가 이미 죽었으면 더 기다릴 이유가 없다
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "오류: 백엔드가 기동 중 종료됐습니다. 로그 마지막 20줄:" >&2
    tail -20 "$LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 0.5
done

echo "오류: 30초 안에 /health가 응답하지 않았습니다. 로그 마지막 20줄:" >&2
tail -20 "$LOG_FILE" >&2
exit 1
