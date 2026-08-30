#!/usr/bin/env bash
# 백엔드(FastAPI/uvicorn) 중지.
#
# 실행 중이 아니어도 성공으로 끝난다(멱등). be-start.sh가 재시작 전에 이 스크립트를
# 호출하므로, 여기서 실패하면 start도 함께 멈춘다.
#
# PID 파일과 포트를 **둘 다** 본다. PID 파일만 믿으면 스크립트 밖에서 띄운 서버나
# 비정상 종료로 남은 파일을 놓친다. 실제로 포트를 잡고 있는 쪽이 진실이다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${BE_PORT:-8080}"
PID_FILE="$ROOT/logs/backend.pid"

# 해당 포트를 LISTEN 중인 PID 목록. 없으면 빈 문자열.
listening_pids() {
  lsof -ti "tcp:$PORT" -sTCP:LISTEN 2>/dev/null || true
}

pids="$(listening_pids)"

# PID 파일에 적힌 프로세스가 살아 있으면 함께 대상에 넣는다.
# uvicorn --reload는 리로더(부모)와 워커(자식)를 함께 띄우므로 포트를 잡은 쪽만
# 죽이면 나머지가 남는다.
if [[ -f "$PID_FILE" ]]; then
  file_pid="$(cat "$PID_FILE" 2>/dev/null || true)"
  if [[ -n "$file_pid" ]] && kill -0 "$file_pid" 2>/dev/null; then
    pids="$pids $file_pid"
    # 리로더의 자식 프로세스까지 포함
    pids="$pids $(pgrep -P "$file_pid" 2>/dev/null || true)"
  fi
fi

pids="$(echo "$pids" | tr ' ' '\n' | grep -E '^[0-9]+$' | sort -u | tr '\n' ' ' || true)"
pids="${pids% }"

if [[ -z "$pids" ]]; then
  echo "백엔드가 실행 중이 아닙니다 (포트 $PORT)."
  rm -f "$PID_FILE"
  exit 0
fi

echo "백엔드 종료 중… PID: $pids (포트 $PORT)"
# shellcheck disable=SC2086
kill $pids 2>/dev/null || true

# 정상 종료를 최대 10초 기다린다. 진행 중인 수집 작업이 청크를 커밋할 여지를 준다.
for _ in $(seq 1 50); do
  [[ -z "$(listening_pids)" ]] && break
  sleep 0.2
done

# 그래도 남아 있으면 강제 종료
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

echo "백엔드를 종료했습니다."
