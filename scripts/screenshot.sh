#!/usr/bin/env bash
# README 스크린샷 재생성: tmux에서 실제 앱을 돌려 캡처 → PNG 렌더
# 사용: scripts/screenshot.sh [replay쿼리] (기본 LYON)
set -e
cd "$(dirname "$0")/.."
Q=${1:-LYON}
tmux kill-session -t lolshot 2>/dev/null || true
tmux new-session -d -s lolshot -x 116 -y 33
tmux send-keys -t lolshot "uv run lolcast replay $Q --speed 300 --game 1" Enter
sleep 8
tmux send-keys -t lolshot d      # 선수 상세
sleep 1
tmux send-keys -t lolshot + + + + + +   # 최대 배속
sleep 25
tmux capture-pane -t lolshot -ep > /tmp/lolcast_pane.ans
tmux kill-session -t lolshot
uv run python scripts/ans2png.py /tmp/lolcast_pane.ans docs/screenshot.png
echo "docs/screenshot.png 갱신 완료"
