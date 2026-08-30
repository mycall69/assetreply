#!/usr/bin/env bash
# 프론트엔드(Next.js dev 서버) 시작. 이미 실행 중이면 먼저 종료하고 재시작한다.
#
# 종료 로직은 fe-stop.sh 하나에만 둔다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${FE_PORT:-3030}"
LOG_DIR="$ROOT/logs"
LOG_FILE="$LOG_DIR/frontend.log"
PID_FILE="$LOG_DIR/frontend.pid"

# ── 사전 점검 ──
if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
  echo "오류: 프론트엔드 의존성이 설치되지 않았습니다 → $ROOT/frontend/node_modules" >&2
  echo "  설치: cd frontend && npm install" >&2
  exit 1
fi

# ── 실행 중이면 종료 (요구사항: 돌고 있으면 스탑 후 재시작) ──
"$ROOT/fe-stop.sh"

mkdir -p "$LOG_DIR"

# 포트를 명시한다. 생략하면 next가 포트 충돌 시 조용히 다른 포트로 옮겨가서
# 스크립트가 보고한 주소와 실제 주소가 어긋난다.
echo "프론트엔드 시작 중… (포트 $PORT)"
cd "$ROOT/frontend"
nohup npm run dev -- --port "$PORT" >>"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

# ── 기동 확인: 응답할 때까지 최대 60초 대기 ──
# dev 서버는 첫 요청에서 컴파일하므로 백엔드보다 여유를 둔다.
for _ in $(seq 1 120); do
  if curl -sS -o /dev/null --max-time 5 "http://localhost:$PORT/" 2>/dev/null; then
    echo "프론트엔드 준비 완료 → http://localhost:$PORT (PID $(cat "$PID_FILE"))"
    echo "  로그: $LOG_FILE"
    exit 0
  fi
  if ! kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "오류: 프론트엔드가 기동 중 종료됐습니다. 로그 마지막 20줄:" >&2
    tail -20 "$LOG_FILE" >&2
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 0.5
done

echo "오류: 60초 안에 응답하지 않았습니다. 로그 마지막 20줄:" >&2
tail -20 "$LOG_FILE" >&2
exit 1
