#!/usr/bin/env bash
# راه انداز سریع داشبورد وب پول هوشمند داوجونز
cd "$(dirname "$0")"
PORT="${1:-8080}"
echo "🌐 داشبورد در حال اجرا: http://localhost:$PORT"
exec .venv/bin/python server.py --port "$PORT"
