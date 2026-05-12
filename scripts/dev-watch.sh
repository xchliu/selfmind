#!/bin/bash
# scripts/dev-watch.sh
# 启动开发自动重建守护（后台运行）
# 检测 selfmind_app/ 和 server.py 的文件变化，自动重建 Docker 容器

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/dev-watch.log"

mkdir -p "$PROJECT_DIR/logs"
cd "$PROJECT_DIR"

# 杀掉旧进程
pkill -f "dev-watch.py" 2>/dev/null || true
sleep 1

# 后台启动
nohup python3 scripts/dev-watch.py >> "$LOG_FILE" 2>&1 &
PID=$!
echo "dev-watch 已启动 (PID=$PID)"
echo "日志: $LOG_FILE"
echo "查看日志: tail -f $LOG_FILE"
