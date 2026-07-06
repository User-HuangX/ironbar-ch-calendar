#!/usr/bin/env sh
# ironbar 点击日历按钮时调用。
set -eu

PROJECT_DIR="/home/hx/Project/ironbar-ch-calendar"
cd "$PROJECT_DIR"

if [ -x "$PROJECT_DIR/.venv/bin/ironbar-ch-calendar" ]; then
    exec "$PROJECT_DIR/.venv/bin/ironbar-ch-calendar"
fi

if command -v uv >/dev/null 2>&1; then
    exec uv run python "$PROJECT_DIR/main.py"
fi

exec python "$PROJECT_DIR/main.py"
