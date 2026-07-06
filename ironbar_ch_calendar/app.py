"""应用入口。GTK4 + gtk4-layer-shell 日历弹窗。"""

from __future__ import annotations

import argparse
import logging
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="从 ironbar 打开的中文日历弹窗")
    parser.add_argument("--debug", action="store_true", help="输出调试日志")
    return parser


def configure_logging(debug: bool = False) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s：%(message)s")


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.debug)

    from ironbar_ch_calendar.layer_shell import run_layer_shell_calendar

    return run_layer_shell_calendar()
