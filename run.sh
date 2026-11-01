#!/usr/bin/env bash
# 启动网页模式：bash run.sh [--port 8771] [--host 127.0.0.1]
cd "$(dirname "$0")" || exit 1
exec python3 bili_planner.py "$@"
