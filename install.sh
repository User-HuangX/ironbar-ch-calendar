#!/usr/bin/env bash
# ironbar-ch-calendar 一键安装脚本
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; CYAN='\033[0;36m'; NC='\033[0m'
info()  { echo -e "${CYAN}→${NC} $*"; }
ok()    { echo -e "${GREEN}✓${NC} $*"; }
err()   { echo -e "${RED}✗${NC} $*"; exit 1; }

PROJECT_DIR="${HOME}/Project/ironbar-ch-calendar"
IRONBAR_CONFIG="${HOME}/.config/ironbar"
LAUNCH_SCRIPT="${IRONBAR_CONFIG}/launch-calendar.sh"

echo "========================================="
echo "  ironbar-ch-calendar 安装"
echo "========================================="
echo ""

# ── 系统依赖 ──────────────────────────────────────────────
info "检查系统依赖..."

if command -v pacman &>/dev/null; then
    MISSING=""
    pacman -Q gtk4         &>/dev/null || MISSING="$MISSING gtk4"
    pacman -Q gtk4-layer-shell &>/dev/null || MISSING="$MISSING gtk4-layer-shell"
    if [ -n "$MISSING" ]; then
        echo "  需要安装:$MISSING"
        sudo pacman -S --noconfirm $MISSING
    fi
elif command -v apt &>/dev/null; then
    MISSING=""
    dpkg -l | grep -q libgtk-4-dev   || MISSING="$MISSING libgtk-4-dev"
    dpkg -l | grep -q libgtk4-layer-shell-dev || MISSING="$MISSING libgtk4-layer-shell-dev"
    if [ -n "$MISSING" ]; then
        sudo apt install -y $MISSING
    fi
else
    info "未检测到 pacman/apt，请手动安装 gtk4 和 gtk4-layer-shell"
fi

# Python 版本
PY=$(python3 --version 2>/dev/null | grep -oP '\d+\.\d+' || echo "0")
if (( $(echo "$PY < 3.12" | bc -l) 2>/dev/null )); then
    err "需要 Python >= 3.12，当前 $PY"
fi
ok "Python $PY"

# ── uv ─────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    info "安装 uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi
ok "uv $(uv --version 2>/dev/null | head -1)"

# ── 项目目录 ───────────────────────────────────────────────
if [ -d "$PROJECT_DIR" ]; then
    info "项目目录已存在，更新..."
    cd "$PROJECT_DIR"
    git pull --rebase 2>/dev/null || true
else
    info "克隆项目..."
    mkdir -p "$(dirname "$PROJECT_DIR")"
    git clone https://github.com/User-HuangX/ironbar-ch-calendar.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ── Python 依赖 ────────────────────────────────────────────
info "安装 Python 依赖..."
uv sync
ok "依赖安装完成"

# ── 启动脚本 ──────────────────────────────────────────────
info "部署 ironbar 启动脚本..."
mkdir -p "$IRONBAR_CONFIG"
cp "$PROJECT_DIR/ironbar/launch-calendar.sh" "$LAUNCH_SCRIPT"
chmod +x "$LAUNCH_SCRIPT"
ok "启动脚本 → $LAUNCH_SCRIPT"

# ── ironbar 配置提示 ──────────────────────────────────────
echo ""
echo "========================================="
echo "  ironbar 配置"
echo "========================================="
echo ""
echo "在 ~/.config/ironbar/config.corn 中添加时钟组件:"
echo ""
echo -e "${CYAN}  \$clock = {"
echo "      type = \"label\""
echo "      name = \"clock\""
echo "      label = \"{{1000:/path/to/clock-label}}\""
echo "      on_click_left = \"$LAUNCH_SCRIPT\""
echo "      justify = \"center\""
echo -e "  }${NC}"
echo ""
echo "并将 \$clock 加入 start/center/end 区域:"
echo ""
echo -e "${CYAN}  center = [ \$clock ]${NC}"
echo ""
ok "安装完成！点击 ironbar 时钟即可使用。"
