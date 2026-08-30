#!/usr/bin/env bash
# 백엔드와 프론트엔드를 한 번에 중지한다. 실행 중이 아니어도 성공으로 끝난다(멱등).
#
# start.sh와 달리 **첫 실패에서 멈추지 않는다.** 정리 작업에서 한쪽이 실패했다고
# 나머지를 남겨두면 다음 시작이 포트 충돌로 깨진다. 둘 다 시도한 뒤 결과를 합산한다.
# 프론트엔드를 먼저 내리는 것은 시작의 역순이다.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=0

echo "▶ 프론트엔드"
"$ROOT/fe-stop.sh" || failed=1

echo
echo "▶ 백엔드"
"$ROOT/be-stop.sh" || failed=1

echo
if [[ $failed -ne 0 ]]; then
  echo "일부를 종료하지 못했습니다. 위 메시지를 확인하세요." >&2
  exit 1
fi

echo "모두 종료했습니다."
