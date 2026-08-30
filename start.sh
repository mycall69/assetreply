#!/usr/bin/env bash
# 백엔드와 프론트엔드를 한 번에 시작한다. 각각 이미 실행 중이면 재시작한다.
#
# 실제 기동 로직은 be-start.sh / fe-start.sh에 있고 여기서는 순서와 요약만 맡는다.
# 백엔드를 먼저 띄우는 이유는 프론트엔드가 /api/fx/* 를 백엔드로 프록시하기 때문이다
# (frontend/next.config.ts, research R13).
#
# 백엔드가 실패하면 프론트엔드를 띄우지 않고 멈춘다. 프록시 대상이 없는 UI는
# 화면만 뜨고 아무것도 못 하므로, 절반만 뜬 상태로 두는 것이 더 헷갈린다.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BE_PORT="${BE_PORT:-8080}"
FE_PORT="${FE_PORT:-3030}"

echo "▶ 백엔드"
if ! "$ROOT/be-start.sh"; then
  echo >&2
  echo "백엔드 시작에 실패해 프론트엔드는 띄우지 않았습니다." >&2
  exit 1
fi

echo
echo "▶ 프론트엔드"
if ! "$ROOT/fe-start.sh"; then
  echo >&2
  echo "프론트엔드 시작에 실패했습니다. 백엔드는 http://localhost:$BE_PORT 에서 계속 실행 중입니다." >&2
  echo "  전부 내리려면: ./stop.sh" >&2
  exit 1
fi

echo
echo "────────────────────────────────────────────"
echo "  UI    http://localhost:$FE_PORT"
echo "  API   http://localhost:$BE_PORT"
echo
echo "  브라우저는 $FE_PORT 만 사용합니다 (API는 프록시됨)."
echo "  중지: ./stop.sh"
echo "────────────────────────────────────────────"
