# AGENTS.md

本文件面向在本仓库中工作的自动化编码代理和协作者。所有新增代码、注释、文档、日志、提交说明和用户可见文案都应优先使用简体中文，除非第三方 API、协议字段、包名、命令或错误原文必须保留英文。

## 项目定位

这是一个基于 ironbar 和 PyQt6 的自定义日历项目。预期使用方式是：用户点击 ironbar 顶部或模块中的日历入口后，自动拉起本项目提供的桌面日历窗口。

核心目标：

- 提供轻量、启动快、适合从状态栏触发的 PyQt6 日历窗口。
- 支持公历日期、中文农历日期、传统节日和法定节假日展示。
- 保持所有面向用户的输出为中文，包括窗口文本、日志、错误提示和文档。

## 当前技术栈

- Python 版本：`>=3.12`
- GUI 框架：PyQt6
- 包配置：`pyproject.toml`
- 入口文件：`main.py`

如果新增依赖，优先写入 `pyproject.toml`，并在 `README.md` 中说明用途。农历和节假日能力可以使用成熟库，但必须在代码中封装清晰边界，避免 UI 层直接散落节假日计算逻辑。

## 推荐命令

开发前先确认本地环境：

```bash
python --version
python main.py
```

如果项目使用 `uv` 管理依赖，优先使用：

```bash
uv sync
uv run python main.py
```

新增测试后，优先提供以下命令：

```bash
uv run pytest
```

若当前环境未安装 `uv` 或 `pytest`，不要盲目假设命令可用；先检查 `pyproject.toml` 和仓库现状，再给出最小可执行替代命令。

## 代码规范

- 所有新增注释使用中文，解释“为什么这样做”和关键业务约束，避免逐行翻译代码。
- 用户可见字符串必须为中文；第三方库异常可保留原文，但外层提示应补充中文上下文。
- 函数和类名可以使用英文，保持 Python 社区习惯；业务概念应命名清晰，例如 `LunarDateService`、`HolidayProvider`、`CalendarWindow`。
- UI、农历计算、节假日数据、ironbar 集成入口应尽量分层，避免把所有逻辑堆在 `main.py`。
- 保持启动路径简单，点击 ironbar 后应尽快显示窗口；耗时初始化应延后或缓存。
- 不要引入网络请求作为日历启动的必需步骤；节假日数据应优先本地可用。

## 日志规范

- 日志内容使用中文。
- 日志应说明动作、结果和关键上下文，例如日期、配置路径、加载的数据源。
- 错误日志必须包含中文说明，不要只输出异常堆栈。
- 避免在正常点击打开日历时输出大量调试日志，默认日志应克制。

建议日志风格：

```python
logger.info("日历窗口已启动")
logger.warning("未找到节假日数据文件，将仅显示基础农历信息")
logger.exception("加载节假日数据失败：%s", data_path)
```

## 农历与节假日要求

实现或修改日期能力时，必须满足以下约束：

- 公历日期必须能对应显示中文农历日期。
- 需要识别常见传统节日，例如春节、元宵节、清明节、端午节、中秋节、重阳节、除夕。
- 需要支持中国法定节假日和调休信息；如果数据只覆盖特定年份，必须在文档或日志中明确说明覆盖范围。
- 节假日数据应有清晰来源和更新方式，不要把不明来源的大段数据直接塞进 UI 代码。
- 当某天同时命中农历节日和法定节假日时，UI 应能稳定展示，不应互相覆盖导致信息丢失。

推荐设计边界：

- `calendar` 或 `services` 模块负责日期、农历、节假日计算。
- `ui` 模块只负责展示，不直接维护节假日规则。
- `data` 目录可存放本地节假日数据文件，并在 README 中说明更新方式。

## ironbar 集成要求

ironbar 负责触发，本项目负责显示日历。修改启动逻辑时要注意：

- `main.py` 应保持为稳定入口，方便 ironbar 通过命令直接调用。
- 程序应支持重复点击的合理行为，例如复用已有窗口、切换显示或快速退出旧实例；具体策略必须在 README 中说明。
- 不要把 ironbar 配置硬编码进业务逻辑。若需要示例配置，应放在文档中。
- 如果新增命令行参数，参数名和帮助说明应保持中文友好，并兼容从 shell 或 ironbar 配置中调用。

## Wayland / niri 弹窗定位

### 最终方案：wlr-layer-shell

日历窗口通过 **`zwlr_layer_shell_v1`** 协议创建 layer surface，锚定在屏幕顶部 ironbar 下方。
这是 fuzzel、SwayNotificationCenter、wofi 等所有 Wayland 覆盖窗口应用的标准做法。

技术栈：**GTK4** + **gtk4-layer-shell** + **Cairo**（渲染）

- `Gtk4LayerShell.set_layer(TOP)` — 在 top 层显示
- `Gtk4LayerShell.set_anchor(TOP, True)` — 锚定顶部
- `Gtk4LayerShell.set_margin(TOP, 30)` — ironbar 高度偏移
- `Gtk4LayerShell.set_keyboard_mode(ON_DEMAND)` — 接收键盘（Esc 关闭）
- `Gtk4LayerShell.set_exclusive_zone(0)` — 不挤压其他窗口

**优势**：
- 零跳变 — 窗口在第一帧就在正确位置（协议保证）
- 无延迟 — 不需要合成器 IPC 或定时器
- 跨合成器 — wlroots 系列（niri/sway/hyprland/river）原生支持
- 无需 niri config 规则

### 注意事项

1. **gtk4-layer-shell 加载顺序**：必须在导入 GTK 之前 `ctypes.CDLL("libgtk4-layer-shell.so")`，否则 layer surface 初始化失败。见 gtk4-layer-shell linking.md。

2. **ironbar 高度自动检测**：`MARGIN_TOP` 在启动时从 `~/.config/ironbar/config.corn` 读取 `height` 字段动态计算，不再硬编码。

3. **窗口关闭**：按 Esc 或 SIGINT/SIGTERM 时关闭。layer-shell 不响应 focus-out（无"点击外部关闭"语义）。

### 过去的方案（已废弃）

~~使用 PyQt6 xdg_toplevel + niri `move-floating-window` IPC 移动窗口。~~
该方案存在不可避免的一帧跳变，违背 niri 设计原则「窗口不应自己跳动」。

### 依赖

- `gtk4` `gtk4-layer-shell`（系统包）
- `pycairo` `pygobject`（Python 包，见 pyproject.toml）

## 文档要求

仓库文档必须使用中文。`README.md` 至少应覆盖：

- 项目用途和运行效果。
- 安装依赖与运行命令。
- ironbar 调用示例。
- 农历、节假日和调休数据的支持范围。
- 常见问题，例如 PyQt6 环境、Wayland/X11、重复点击行为。

当新增配置项、依赖、命令行参数、节假日数据来源或运行方式时，必须同步更新 README。

## 测试与验证

日历相关改动至少验证：

- 程序可以通过 `python main.py` 或 `uv run python main.py` 启动。
- 今天日期能正常显示。
- 至少抽查春节、中秋节、端午节、国庆节等关键日期。
- 节假日数据缺失或年份不覆盖时，程序不会崩溃，并给出中文日志。

如果新增自动化测试，优先覆盖纯逻辑模块，例如农历转换、节假日匹配、日期格式化。GUI 测试可以后置，但不要让业务逻辑只能通过打开窗口验证。

## 协作约束

- 修改前先查看当前文件结构，保持改动范围小。
- 不要覆盖用户尚未提交的改动。
- 不要删除现有功能或依赖，除非用户明确要求。
- 新增文件和目录应有明确职责，避免过早搭建复杂框架。
- 完成改动后说明修改了哪些文件、如何验证，以及仍未覆盖的风险。
