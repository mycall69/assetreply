#!/usr/bin/env bash
# 프론트엔드(Next.js dev 서버) 중지.
#
# 실행 중이 아니어도 성공으로 끝난다(멱등). fe-start.sh가 재시작 전에 호출한다.
# `next dev`는 자식 프로세스를 띄우므로 PID 파일 하나만으로는 부족하고,
# 실제로 포트를 잡고 있는 프로세스를 함께 찾는다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${FE_PORT:-3030}"
PID_FILE="$ROOT/logs/frontend.pid"

listening_pids() {
  lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true
}

pids="$(listening_pids)"

if [[ -f "$PID_FILE" ]]; then
  file_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$file_pid" ]] && kill -0 "$file_pid" 2>/dev/null; then
    pids="$pids $file_pid"
    # npm run dev → next dev 로 이어지는 자식까지 포함
    pids="$pids $(pgrep -P "$file_pid" 2>/dev/null || true)"
  fi
fi

pids="$(echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u | tr '\n' ' ' || true)"
pids="${pids% }"

if [[ -z "$pids" ]]; then
  echo "프론트엔드가 실행 중이 아닙니다 (포트 $PORT)."
  rm -f "$PID_FILE"
  exit 0
fi

echo "프론트엔드 종료 중… PID: $pids (포트 $PORT)"
# shellcheck disable=SC2086
kill $pids 2>/dev/null || true

for _ in $(seq 1 50); do
  [[ -z "$(listening_pids)" ]] && break
  sleep 0.2
done

remaining="$(listening_pids)"
if [[ -n "$remaining" ]]; then
  echo "정상 종료에 응답하지 않아 강제 종료합니다: $remaining"
  # shellcheck disable=SC2086
  kill -9 $remaining 2>/dev/null || true
  sleep 0.5
fi

rm -f "$PID_FILE"

if [[ -n "$(listening_pids)" ]]; then
  echo "오류: 포트 $PORT가 여전히 점유되어 있습니다." >&2
  exit 1
fi

echo "프론트엔드를 종료했습니다."
