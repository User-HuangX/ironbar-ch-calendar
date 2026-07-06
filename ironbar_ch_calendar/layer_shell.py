"""wlr-layer-shell 日历弹窗（GTK4 + gtk4-layer-shell）。"""

from __future__ import annotations

import calendar
import ctypes
import logging
import os
import re
import signal
from datetime import date
from pathlib import Path

import cairo

ctypes.CDLL("libgtk4-layer-shell.so")

import gi  # noqa: E402

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gtk, Gtk4LayerShell  # noqa: E402

from .calendar_service import CalendarService

logger = logging.getLogger(__name__)

W, H = 560, 500
HEADER_H = 42
FOOTER_H = 52
CELL_W, CELL_H = 68, 56
GRID_X = 24
GRID_Y = HEADER_H + 24
GAP = 6
R = 8  # 单元格圆角

FONT = "Noto Sans CJK SC"


def _font(cr, size, weight=cairo.FontWeight.NORMAL):
    cr.select_font_face(FONT, cairo.FontSlant.NORMAL, weight)
    cr.set_font_size(size)


def _detect_ironbar_height() -> int:
    for p in [Path.home() / ".config/ironbar/config.corn",
              Path.home() / ".config/ironbar/config.toml"]:
        if p.exists():
            try:
                m = re.search(r'height\s*=\s*(\d+)', p.read_text())
                if m:
                    return int(m.group(1))
            except OSError:
                pass
    return 30


MARGIN_TOP = _detect_ironbar_height() - 10

# ── 轻量浅色主题（贴近透明 WM / ironbar）──────────────────
# 不使用窗口级透明，避免文字一起变淡；通过更浅的冷灰面板降低压迫感。
BG = (0.930, 0.945, 0.965)            # #EDF1F6
HEADER_BG = (0.900, 0.920, 0.945)     # #E6EAF1
FOOTER_BG = (0.900, 0.920, 0.945)     # #E6EAF1
TEXT = (0.120, 0.145, 0.180)          # #1F2530
TEXT_MUTED = (0.430, 0.470, 0.530)    # #6E7887
TEXT_WEEKEND = (0.570, 0.180, 0.220)  # 褐红，保证浅粉底上的对比度
TEXT_HOLIDAY = (0.720, 0.430, 0.160)  # 柔和琥珀，不用警报红
ACCENT = (0.255, 0.455, 0.760)        # 灰蓝主色
ACCENT_BG = (0.810, 0.865, 0.955)     # 浅蓝今日底
HOVER_BG = (0.870, 0.895, 0.930)      # 轻 hover
BTN_BG = (0.905, 0.925, 0.950)        # 浅按钮底
BTN_HOVER = (0.835, 0.875, 0.930)     # 浅蓝 hover
DIVIDER = (0.760, 0.795, 0.845)       # 冷灰分割线
BORDER = (0.690, 0.735, 0.795)        # 外框
WEEKEND_TINT = (0.940, 0.905, 0.915)  # 极淡暖色列底
WHITE = (0.980, 0.985, 0.995)         # 选中态文字

# 按钮专用
CLOSE_DEFAULT = (0.430, 0.470, 0.530)
CLOSE_HOVER = (0.760, 0.220, 0.260)
ARROW_DEFAULT = (0.400, 0.445, 0.510)
ARROW_HOVER = (0.120, 0.145, 0.180)

# 今日光环
GLOW_OUTER = (0.600, 0.710, 0.900)
GLOW_INNER = ACCENT

# 角标颜色保留给后续事件功能，当前视觉方案默认不绘制角标
HOLIDAY_DOT = TEXT_HOLIDAY
FESTIVAL_DOT = TEXT_HOLIDAY
ADJUSTED_DOT = TEXT_MUTED


def _rgb(cr, rgb):
    cr.set_source_rgb(*rgb)


class CalendarWidget(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self._svc = CalendarService()
        t = date.today()
        self._year, self._month, self._sel = t.year, t.month, t
        self._hover_cell: tuple[int, int] | None = None
        self._hover_btn: str | None = None
        self.set_size_request(W, H)
        self.set_draw_func(self._on_draw)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        motion.connect("leave", self._on_leave)
        self.add_controller(motion)

        click = Gtk.GestureClick.new()
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key)
        self.add_controller(key)

    # ── 日历逻辑 ────────────────────────────────────────────

    def _prev_month(self):
        if self._month == 1: self._year -= 1; self._month = 12
        else: self._month -= 1
        self._sel = date(self._year, self._month, 1)
        self.queue_draw()

    def _next_month(self):
        if self._month == 12: self._year += 1; self._month = 1
        else: self._month += 1
        self._sel = date(self._year, self._month, 1)
        self.queue_draw()

    def _go_today(self):
        t = date.today()
        self._year, self._month, self._sel = t.year, t.month, t
        self._svc = CalendarService(today=t)
        self.queue_draw()

    def _click_cell(self, col, row):
        md = calendar.Calendar(firstweekday=0).monthdatescalendar(self._year, self._month)
        if row < len(md) and col < 7:
            d = md[row][col]
            self._sel = d
            if d.month != self._month or d.year != self._year:
                self._year, self._month = d.year, d.month
            self.queue_draw()

    def _hit_cell(self, px, py):
        for row in range(6):
            for col in range(7):
                cx = GRID_X + col * CELL_W
                cy = GRID_Y + row * CELL_H
                if cx <= px < cx + CELL_W and cy <= py < cy + CELL_H:
                    return (col, row)
        return None

    # ── 输入 ────────────────────────────────────────────────

    def _on_motion(self, controller, x, y):
        old_cell, old_btn = self._hover_cell, self._hover_btn
        self._hover_cell = self._hit_cell(x, y)
        self._hover_btn = self._hit_header(x, y)
        if old_cell != self._hover_cell or old_btn != self._hover_btn:
            self.queue_draw()

    def _on_leave(self, controller):
        if self._hover_cell or self._hover_btn:
            self._hover_cell = self._hover_btn = None
            self.queue_draw()

    def _hit_header(self, x, y):
        if 4 <= y < HEADER_H - 4:
            if x < 40: return "prev"
            if W - 130 <= x < W - 82: return "today"
            if W - 55 <= x < W - 35: return "next"
            if W - 30 <= x < W: return "close"
        return None

    def _on_click(self, gesture, n_press, x, y):
        btn = self._hit_header(x, y)
        if btn == "prev": self._prev_month()
        elif btn == "today": self._go_today()
        elif btn == "next": self._next_month()
        elif btn == "close": self.get_root().close()
        else:
            cell = self._hit_cell(x, y)
            if cell: self._click_cell(*cell)

    def _on_key(self, controller, keyval, keycode, state):
        if keyval == 65307: self.get_root().close(); return True
        return False

    # ── 渲染 ────────────────────────────────────────────────

    def _on_draw(self, area, cr, w, h):
        _rgb(cr, BG); cr.paint()
        self._draw_header(cr)
        self._draw_weekend_tint(cr)
        self._draw_weekdays(cr)
        self._draw_cells(cr)
        self._draw_footer(cr)
        _rgb(cr, BORDER)
        cr.set_line_width(1)
        cr.rectangle(0.5, 0.5, w - 1, h - 1)
        cr.stroke()

    # ── 头部 ────────────────────────────────────────────────

    def _draw_header(self, cr):
        _rgb(cr, HEADER_BG)
        cr.rectangle(0, 0, W, HEADER_H); cr.fill()

        _rgb(cr, TEXT)
        _font(cr, 15, cairo.FontWeight.BOLD)
        title = f"{self._year} 年 {self._month} 月"
        ext = cr.text_extents(title)
        cr.move_to(W / 2 - ext.width / 2, 29); cr.show_text(title)

        # prev / next 箭头（hover 变色 + 下划线）
        self._draw_arrow(cr, "‹", 14, 29, "prev")
        self._draw_arrow(cr, "›", W - 50, 29, "next")

        # 关闭按钮
        cx, cy, r = W - 20, 21, 5.5
        is_close_hover = self._hover_btn == "close"
        lw = 2.5 if is_close_hover else 1.8
        color = CLOSE_HOVER if is_close_hover else CLOSE_DEFAULT

        if is_close_hover:
            _rgb(cr, (0.975, 0.865, 0.875))
            cr.set_line_width(1)
            cr.arc(cx, cy, 11, 0, 6.283); cr.stroke()

        _rgb(cr, color)
        cr.set_line_width(lw)
        cr.move_to(cx - r, cy - r); cr.line_to(cx + r, cy + r); cr.stroke()
        cr.move_to(cx + r, cy - r); cr.line_to(cx - r, cy + r); cr.stroke()

        # 今天按钮：默认只用细边框，避免在头部形成第二个强焦点
        bx, by, bw, bh = W - 124, 10, 52, 22
        if self._hover_btn == "today":
            _rgb(cr, BTN_HOVER)
            _rrect(cr, bx, by, bw, bh, 10); cr.fill()
            label_color = TEXT
        else:
            _rgb(cr, BORDER)
            cr.set_line_width(1)
            _rrect(cr, bx, by, bw, bh, 10); cr.stroke()
            label_color = TEXT_MUTED
        _rgb(cr, label_color)
        _font(cr, 11, cairo.FontWeight.BOLD)
        t_ext = cr.text_extents("今天")
        cr.move_to(bx + bw / 2 - t_ext.width / 2, by + 15); cr.show_text("今天")

    def _draw_arrow(self, cr, text, x, y, name):
        is_hover = self._hover_btn == name
        color = ARROW_HOVER if is_hover else ARROW_DEFAULT
        wt = cairo.FontWeight.BOLD if is_hover else cairo.FontWeight.NORMAL
        _rgb(cr, color)
        _font(cr, 16, wt)
        cr.move_to(x, y); cr.show_text(text)
        if is_hover:
            _rgb(cr, ACCENT)
            cr.set_line_width(2)
            ext = cr.text_extents(text)
            cr.move_to(x, y + 4); cr.line_to(x + ext.width, y + 4)
            cr.stroke()

    # ── 周末列底色 ──────────────────────────────────────────

    def _draw_weekend_tint(self, cr):
        _rgb(cr, WEEKEND_TINT)
        for col in (5, 6):
            cr.rectangle(GRID_X + col * CELL_W, GRID_Y, CELL_W - GAP, 6 * CELL_H - GAP)
            cr.fill()

    # ── 星期行 ──────────────────────────────────────────────

    def _draw_weekdays(self, cr):
        _rgb(cr, TEXT_MUTED)
        _font(cr, 11)
        for i, d in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            ext = cr.text_extents(d)
            x = GRID_X + i * CELL_W + (CELL_W - ext.width) / 2
            cr.move_to(x, GRID_Y - 9); cr.show_text(d)

    # ── 日期格 ──────────────────────────────────────────────

    def _draw_cells(self, cr):
        md = calendar.Calendar(firstweekday=0).monthdatescalendar(self._year, self._month)
        today = date.today()
        for row, week in enumerate(md):
            for col, d in enumerate(week):
                info = self._svc.get_day_info(d)
                x = GRID_X + col * CELL_W
                y = GRID_Y + row * CELL_H
                self._draw_cell(cr, x, y, d, info, today, col, row)

    def _draw_cell(self, cr, x, y, d, info, today, col, row):
        cw, ch = CELL_W - GAP, CELL_H - GAP
        cx, cy = x + GAP / 2, y + GAP / 2
        r = R
        in_month = d.month == self._month
        is_today = d == today
        is_sel = d == self._sel
        is_hover = self._hover_cell == (col, row)
        is_weekend = col >= 5

        # 背景
        if is_sel:
            _rgb(cr, ACCENT)
        elif is_today:
            pass  # 在光环部分处理
        elif is_hover:
            _rgb(cr, HOVER_BG)
        else:
            cr.set_source_rgba(0, 0, 0, 0)
        _rrect(cr, cx, cy, cw, ch, r)
        if not (is_today and not is_sel):
            cr.fill()

        # 今日光环（双层）
        if is_today and not is_sel:
            _rgb(cr, GLOW_OUTER)
            cr.set_line_width(4)
            _rrect(cr, cx - 0.5, cy - 0.5, cw + 1, ch + 1, r + 1); cr.stroke()
            _rgb(cr, ACCENT_BG)
            _rrect(cr, cx, cy, cw, ch, r); cr.fill()
            _rgb(cr, ACCENT)
            cr.set_line_width(2)
            _rrect(cr, cx + 1, cy + 1, cw - 2, ch - 2, r - 1); cr.stroke()

        # 选中格边框
        if is_sel:
            _rrect(cr, cx, cy, cw, ch, r); cr.fill()

        # 文字颜色
        if is_sel: fg = WHITE
        elif info.holiday_name and in_month: fg = TEXT_HOLIDAY
        elif is_weekend and in_month: fg = TEXT_WEEKEND
        elif not in_month: fg = TEXT_MUTED
        else: fg = TEXT

        _rgb(cr, fg)
        _font(cr, 15, cairo.FontWeight.BOLD if is_today else cairo.FontWeight.NORMAL)
        ds = str(d.day)
        ext = cr.text_extents(ds)
        cr.move_to(cx + cw / 2 - ext.width / 2, cy + 23); cr.show_text(ds)

        # 节日不再绘制彩色角标，避免和今日强调色竞争。
        # 节日信息保留在副文本和底部信息栏中。

        # 农历
        sub = info.badge or info.lunar_label
        _font(cr, 10)
        _rgb(cr, WHITE if is_sel else TEXT_MUTED)
        ext2 = cr.text_extents(sub)
        cr.move_to(cx + cw / 2 - ext2.width / 2, cy + 39); cr.show_text(sub)

    # ── 底部 ────────────────────────────────────────────────

    def _draw_footer(self, cr):
        fy = H - FOOTER_H
        _rgb(cr, FOOTER_BG)
        cr.rectangle(0, fy, W, FOOTER_H); cr.fill()

        _rgb(cr, DIVIDER)
        cr.set_line_width(1.5)
        cr.move_to(0, fy); cr.line_to(W, fy); cr.stroke()

        info = self._svc.get_day_info(self._sel)

        # 日期 pill
        px, py, pw, ph = 16, fy + 10, 42, 32
        _rgb(cr, ACCENT)
        _rrect(cr, px, py, pw, ph, 8); cr.fill()
        _rgb(cr, WHITE)
        _font(cr, 24, cairo.FontWeight.BOLD)
        ds = f"{self._sel.day:02d}"
        ext = cr.text_extents(ds)
        cr.move_to(px + pw / 2 - ext.width / 2, py + 24); cr.show_text(ds)

        # 信息文本
        parts = [info.weekday, info.lunar_label]
        if info.festival: parts.append(info.festival)
        if info.holiday_name: parts.append(info.holiday_name)
        detail = " · ".join(parts)

        _rgb(cr, TEXT)
        _font(cr, 13)
        cr.move_to(px + pw + 14, fy + 24); cr.show_text(detail)

        # 节日下划线
        if info.holiday_name or info.festival:
            ext_d = cr.text_extents(detail)
            _rgb(cr, TEXT_HOLIDAY)
            cr.set_line_width(2)
            cr.move_to(px + pw + 14, fy + 31)
            cr.line_to(px + pw + 14 + min(ext_d.width, 220), fy + 31)
            cr.stroke()


# ── 工具 ────────────────────────────────────────────────────

def _rrect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
    cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
    cr.arc(x + r, y + r, r, 3.14159, 4.71239)
    cr.close_path()


# ── 入口 ────────────────────────────────────────────────────

def run_layer_shell_calendar() -> int:
    Gtk4LayerShell.is_supported()
    app = Gtk.Application()
    app.connect("activate", _on_activate)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    return app.run()


def _on_activate(app: Gtk.Application) -> None:
    win = Gtk.ApplicationWindow(application=app)
    win.set_title("中文日历")
    win.set_resizable(False)

    Gtk4LayerShell.init_for_window(win)
    Gtk4LayerShell.set_namespace(win, "ironbar-ch-calendar")
    Gtk4LayerShell.set_layer(win, Gtk4LayerShell.Layer.TOP)
    Gtk4LayerShell.set_anchor(win, Gtk4LayerShell.Edge.TOP, True)
    Gtk4LayerShell.set_margin(win, Gtk4LayerShell.Edge.TOP, MARGIN_TOP)
    Gtk4LayerShell.set_keyboard_mode(win, Gtk4LayerShell.KeyboardMode.EXCLUSIVE)

    _pick_monitor(win)
    win.connect("close-request", lambda *_: app.quit())

    cal = CalendarWidget()
    cal.set_size_request(W, H)
    win.set_child(cal)
    win.present()


def _pick_monitor(win) -> None:
    import subprocess
    try:
        r = subprocess.run(["niri", "msg", "focused-output"],
                           capture_output=True, text=True, timeout=3)
        name = r.stdout.strip()
        if name:
            display = Gtk.Widget.get_display(win)
            for m in display.get_monitors():
                if m.get_connector() == name:
                    Gtk4LayerShell.set_monitor(win, m)
                    return
    except Exception:
        pass
