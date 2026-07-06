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
from gi.repository import Gtk, Gtk4LayerShell, GLib, Gdk  # noqa: E402

from .calendar_service import CalendarService

logger = logging.getLogger(__name__)

W, H = 560, 500
HEADER_H = 40
FOOTER_H = 48
CELL_W, CELL_H = 68, 56
GRID_X = 24
GRID_Y = HEADER_H + 24
GAP = 6

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

# ── 暗色主题 ────────────────────────────────────────────────
BG = (0.12, 0.13, 0.16, 0.40)
HEADER_BG = (0.15, 0.16, 0.19, 0.45)
FOOTER_BG_TOP = (0.15, 0.16, 0.19, 0.45)
FOOTER_BG_BOT = (0.10, 0.11, 0.14, 0.35)
TEXT = (0.90, 0.92, 0.95, 1.0)
TEXT_MUTED = (0.50, 0.53, 0.58, 1.0)
TEXT_WEEKEND = (0.85, 0.45, 0.45, 1.0)
TEXT_HOLIDAY = (0.95, 0.35, 0.35, 1.0)
ACCENT = (0.35, 0.65, 0.95, 1.0)
ACCENT_BG = (0.18, 0.28, 0.45, 0.45)
HOVER_BG = (0.20, 0.22, 0.28, 0.40)
BTN_BG = (0.18, 0.19, 0.23, 0.35)
BTN_HOVER = (0.22, 0.24, 0.29, 0.50)
DIVIDER = (0.20, 0.21, 0.26, 0.70)
WEEKEND_TINT = (0.15, 0.12, 0.12, 0.35)
WHITE = (0.95, 0.96, 0.97, 1.0)
HOLIDAY_DOT = (0.95, 0.35, 0.35, 0.90)
FESTIVAL_DOT = (0.95, 0.65, 0.25, 0.85)


def _rgba(cr, rgba):
    cr.set_source_rgba(*rgba)


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
        _rgba(cr, BG); cr.paint()
        self._draw_header(cr)
        self._draw_weekend_tint(cr)
        self._draw_weekdays(cr)
        self._draw_cells(cr)
        self._draw_footer(cr)

    # ── 头部 ────────────────────────────────────────────────

    def _draw_header(self, cr):
        _rgba(cr, HEADER_BG)
        cr.rectangle(0, 0, W, HEADER_H); cr.fill()

        _rgba(cr, TEXT)
        _font(cr, 15, cairo.FontWeight.BOLD)
        title = f"{self._year} 年 {self._month} 月"
        ext = cr.text_extents(title)
        cr.move_to(W / 2 - ext.width / 2, 28); cr.show_text(title)

        _font(cr, 18)
        cr.move_to(14, 28); cr.show_text("‹")
        cr.move_to(W - 50, 28); cr.show_text("›")

        cx, cy, r = W - 20, 20, 8
        _rgba(cr, (0.85, 0.3, 0.3, 0.9) if self._hover_btn == "close" else TEXT_MUTED)
        cr.set_line_width(2 if self._hover_btn == "close" else 1.8)
        cr.move_to(cx - r / 2, cy - r / 2); cr.line_to(cx + r / 2, cy + r / 2)
        cr.stroke()
        cr.move_to(cx + r / 2, cy - r / 2); cr.line_to(cx - r / 2, cy + r / 2)
        cr.stroke()

        bx, by, bw, bh = W - 124, 9, 52, 22
        _rgba(cr, BTN_HOVER if self._hover_btn == "today" else BTN_BG)
        _rrect(cr, bx, by, bw, bh, 8); cr.fill()
        _rgba(cr, TEXT)
        _font(cr, 12, cairo.FontWeight.BOLD)
        t_ext = cr.text_extents("今天")
        cr.move_to(bx + bw / 2 - t_ext.width / 2, by + 15); cr.show_text("今天")

    # ── 周末列底色 ──────────────────────────────────────────

    def _draw_weekend_tint(self, cr):
        _rgba(cr, WEEKEND_TINT)
        for col in (5, 6):
            cr.rectangle(GRID_X + col * CELL_W, GRID_Y, CELL_W - GAP, 6 * CELL_H - GAP)
            cr.fill()

    # ── 星期行 ──────────────────────────────────────────────

    def _draw_weekdays(self, cr):
        _rgba(cr, TEXT_MUTED)
        _font(cr, 12, cairo.FontWeight.BOLD)
        for i, d in enumerate(("一", "二", "三", "四", "五", "六", "日")):
            ext = cr.text_extents(d)
            x = GRID_X + i * CELL_W + (CELL_W - ext.width) / 2
            cr.move_to(x, GRID_Y - 8); cr.show_text(d)

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
        r = 8 if d in (self._sel, today) else 6
        in_month = d.month == self._month
        is_today = d == today
        is_sel = d == self._sel
        is_hover = self._hover_cell == (col, row)
        is_weekend = col >= 5

        if is_sel:
            _rgba(cr, ACCENT)
        elif is_today:
            _rgba(cr, ACCENT_BG)
        elif is_hover:
            _rgba(cr, HOVER_BG)
        else:
            cr.set_source_rgba(0, 0, 0, 0)
        _rrect(cr, cx, cy, cw, ch, r); cr.fill()

        if is_today and not is_sel:
            _rgba(cr, ACCENT)
            cr.set_line_width(2)
            _rrect(cr, cx, cy, cw, ch, r); cr.stroke()

        if is_sel: fg = WHITE
        elif info.holiday_name and in_month: fg = TEXT_HOLIDAY
        elif is_weekend and in_month: fg = TEXT_WEEKEND
        elif not in_month: fg = (*TEXT_MUTED[:3], 0.35)
        else: fg = TEXT

        _rgba(cr, fg)
        _font(cr, 15, cairo.FontWeight.BOLD if is_today else cairo.FontWeight.NORMAL)
        ds = str(d.day)
        ext = cr.text_extents(ds)
        cr.move_to(cx + cw / 2 - ext.width / 2, cy + 22); cr.show_text(ds)

        has_dot = (info.holiday_name or info.festival) and in_month and not is_sel
        if has_dot:
            _rgba(cr, HOLIDAY_DOT if info.holiday_name else FESTIVAL_DOT)
            cr.arc(cx + cw - 8, cy + 8, 3, 0, 6.283); cr.fill()

        sub = info.badge or info.lunar_label
        _font(cr, 10)
        _rgba(cr, WHITE if is_sel else (*TEXT_MUTED[:3], 0.55))
        ext2 = cr.text_extents(sub)
        cr.move_to(cx + cw / 2 - ext2.width / 2, cy + 40); cr.show_text(sub)

    # ── 底部 ────────────────────────────────────────────────

    def _draw_footer(self, cr):
        fy = H - FOOTER_H
        grad = cairo.LinearGradient(0, fy, 0, H)
        grad.add_color_stop_rgba(0, *FOOTER_BG_TOP)
        grad.add_color_stop_rgba(1, *FOOTER_BG_BOT)
        cr.set_source(grad)
        cr.rectangle(0, fy, W, FOOTER_H); cr.fill()

        _rgba(cr, DIVIDER)
        cr.set_line_width(1)
        cr.move_to(0, fy); cr.line_to(W, fy); cr.stroke()

        info = self._svc.get_day_info(self._sel)
        _rgba(cr, ACCENT)
        _font(cr, 26, cairo.FontWeight.BOLD)
        ds = f"{self._sel.day:02d}"
        d_ext = cr.text_extents(ds)
        cr.move_to(20, fy + 32); cr.show_text(ds)

        parts = [info.weekday, info.lunar_label]
        if info.festival: parts.append(info.festival)
        if info.holiday_name: parts.append(info.holiday_name)
        detail = "  ·  ".join(parts)

        _rgba(cr, TEXT)
        _font(cr, 12)
        cr.move_to(70, fy + 24); cr.show_text(detail)

        _rgba(cr, (*TEXT_MUTED[:3], 0.35))
        _font(cr, 9)
        hint = "Esc 关闭"
        h_ext = cr.text_extents(hint)
        cr.move_to(W - h_ext.width - 16, fy + 34); cr.show_text(hint)


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
    # 背景透明，文字保持不透明
    win.add_css_class("transparent-bg")

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
            from gi.repository import Gdk as _Gdk  # noqa: E402
            display = Gtk.Widget.get_display(win)
            for m in display.get_monitors():
                if m.get_connector() == name:
                    Gtk4LayerShell.set_monitor(win, m)
                    return
    except Exception:
        pass
