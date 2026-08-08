#!/usr/bin/env bash

set -euo pipefail

if [ $# -lt 1 ]; then
  echo "Usage: hang.sh <command> [args...]"
  echo "Example: hang.sh python train.py --epochs 10"
  exit 1
fi

# 时间戳便于浏览，mktemp 后缀确保同一秒启动也不会覆盖或混写。
LOG_DIR="${HANG_LOG_DIR:-./logs}"
mkdir -p -- "$LOG_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOG_FILE=$(mktemp "$LOG_DIR/hang_${TIMESTAMP}.XXXXXX")

# 核心逻辑
nohup "$@" >"$LOG_FILE" 2>&1 &

PID=$!

echo "✔ Command started in background"
echo "✔ PID: $PID"
echo "✔ Log: $LOG_FILE"
echo "✔ Info: ps -p $PID -o pid=,etime=,command="
echo "✔ Stop: kill $PID"
