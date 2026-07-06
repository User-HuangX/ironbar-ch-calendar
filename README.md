# ironbar 中文日历

基于 GTK4 + gtk4-layer-shell + Cairo 的中文日历弹窗。点击 ironbar 时钟后，日历通过 Wayland `zwlr_layer_shell_v1` 协议锚定在屏幕顶部 bar 下方，零跳变、零延迟。

参考实现：fuzzel、SwayNotificationCenter、wofi

## 功能

- 公历 + 农历双显示
- 传统节日（春节、元宵、清明、端午、中秋、重阳、除夕）
- 中国法定节假日 + 调休（通过 chinesecalendar）
- 按 Esc / ✕ / 点击外部关闭
- ironbar 高度自动检测（读取 `~/.config/ironbar/config.corn`）

## 依赖

系统包（Arch）：

```bash
sudo pacman -S gtk4 gtk4-layer-shell
```

Python 包：

```bash
uv sync
```

## 运行

```bash
uv run python main.py
```

或安装后：

```bash
ironbar-ch-calendar
```

## ironbar 配置

```corn
$clock = {
    type = "label"
    name = "clock"
    label = "{{1000:/home/hx/.local/bin/ironbar-clock-label}}"
    on_click_left = "/home/hx/.config/ironbar/launch-calendar.sh"
}
```

**不需要 niri window-rule**——layer-shell 协议自动定位。

## 架构

```
ironbar_ch_calendar/
├── app.py              # 入口
├── layer_shell.py      # GTK4 + gtk4-layer-shell + Cairo 渲染
└── calendar_service.py # 农历/节假日计算
```

## 定位原理

日历使用 `zwlr_layer_shell_v1` 协议创建 layer surface，锚定在 `TOP` 层：

- `Gtk4LayerShell.set_anchor(TOP, True)` — 锚定屏幕顶部
- `Gtk4LayerShell.set_margin(TOP, N)` — ironbar 高度（自动读取配置）
- `Gtk4LayerShell.set_keyboard_mode(EXCLUSIVE)` — 接收键盘 + 点击外部关闭

窗口在第一帧就在正确位置，无合成器 IPC、无跳变。

## 自定义

- **ironbar 高度**：修改 `~/.config/ironbar/config.corn` 中 `height` 值，日历自动适配
- **日历尺寸**：改 `layer_shell.py` 中 `W, H` 常量
- **水平偏移**：改 `GRID_X` 或加 left/right margin
