"""日历、农历和节假日信息服务。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 农历和节假日依赖是增强能力，不应该因为用户暂时没安装依赖就阻止窗口打开。
try:
    from lunardate import LunarDate
except ImportError:  # pragma: no cover - 依赖缺失时仍允许窗口启动
    LunarDate = None  # type: ignore[assignment]
    logger.warning("未安装 lunardate，农历信息将不可用")

try:
    from chinese_calendar import get_holiday_detail, is_holiday, is_workday
except ImportError:  # pragma: no cover - 依赖缺失时仍允许窗口启动
    get_holiday_detail = None  # type: ignore[assignment]
    is_holiday = None  # type: ignore[assignment]
    is_workday = None  # type: ignore[assignment]
    logger.warning("未安装 chinesecalendar，法定节假日和调休信息将不可用")


WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")

# 固定公历节日只和月日有关，法定放假与调休由 chinesecalendar 包提供的 chinese_calendar 模块判断。
SOLAR_FESTIVALS = {
    (1, 1): "元旦",
    (2, 14): "情人节",
    (3, 8): "妇女节",
    (3, 12): "植树节",
    (5, 1): "劳动节",
    (5, 4): "青年节",
    (6, 1): "儿童节",
    (7, 1): "建党节",
    (8, 1): "建军节",
    (9, 10): "教师节",
    (10, 1): "国庆节",
    (12, 24): "平安夜",
    (12, 25): "圣诞节",
}

LUNAR_FESTIVALS = {
    (1, 1): "春节",
    (1, 15): "元宵节",
    (2, 2): "龙抬头",
    (5, 5): "端午节",
    (7, 7): "七夕",
    (7, 15): "中元节",
    (8, 15): "中秋节",
    (9, 9): "重阳节",
    (12, 8): "腊八节",
    (12, 23): "北方小年",
    (12, 24): "南方小年",
}

LUNAR_MONTH_NAMES = (
    "",
    "正月",
    "二月",
    "三月",
    "四月",
    "五月",
    "六月",
    "七月",
    "八月",
    "九月",
    "十月",
    "冬月",
    "腊月",
)

LUNAR_DAY_PREFIX = ("初", "十", "廿", "三")
LUNAR_DAY_NUMBERS = ("", "一", "二", "三", "四", "五", "六", "七", "八", "九", "十")


@dataclass(frozen=True)
class DayInfo:
    """单个公历日期对应的展示信息。"""

    solar_date: date
    weekday: str
    lunar_label: str
    festival: Optional[str]
    holiday_name: Optional[str]
    is_day_off: bool
    is_adjusted_workday: bool
    is_today: bool

    @property
    def badge(self) -> Optional[str]:
        """优先展示法定节假日，其次展示传统节日。"""

        if self.holiday_name:
            return self.holiday_name
        return self.festival


class CalendarService:
    """提供 UI 层需要的中文日历信息。"""

    def __init__(self, today: Optional[date] = None) -> None:
        self.today = today or date.today()

    def get_day_info(self, solar_date: date) -> DayInfo:
        # UI 只依赖 DayInfo，不需要知道农历库、节假日库或降级逻辑的细节。
        lunar_label, lunar_festival, is_lunar_available = self._lunar_info(solar_date)
        solar_festival = SOLAR_FESTIVALS.get((solar_date.month, solar_date.day))
        qingming = "清明节" if self._is_qingming(solar_date) else None
        festival = qingming or lunar_festival or solar_festival
        holiday_name, is_day_off, is_adjusted_workday = self._holiday_info(solar_date)

        # 没有官方调休库时，至少把周末和固定节日展示为休息参考。
        if not is_lunar_available and festival in {"春节", "端午节", "中秋节"}:
            logger.warning(
                "农历依赖不可用，无法确认 %s 的农历节日", solar_date.isoformat()
            )
        if is_holiday is None:
            is_day_off = solar_date.weekday() >= 5

        return DayInfo(
            solar_date=solar_date,
            weekday=WEEKDAY_NAMES[solar_date.weekday()],
            lunar_label=lunar_label,
            festival=festival,
            holiday_name=holiday_name,
            is_day_off=is_day_off,
            is_adjusted_workday=is_adjusted_workday,
            is_today=solar_date == self.today,
        )

    def _lunar_info(self, solar_date: date) -> tuple[str, Optional[str], bool]:
        if LunarDate is None:
            return "农历不可用", None, False

        # lunardate 返回的是农历月日；这里统一转换为适合日历格子显示的中文短标签。
        lunar = LunarDate.fromSolarDate(
            solar_date.year, solar_date.month, solar_date.day
        )
        lunar_month = int(lunar.month)
        lunar_day = int(lunar.day)
        is_leap = bool(getattr(lunar, "isLeapMonth", False))
        festival = LUNAR_FESTIVALS.get((lunar_month, lunar_day))

        # 除夕取决于当年腊月最后一天，不能硬编码为腊月三十。
        tomorrow = solar_date.toordinal() + 1
        try:
            next_day_lunar = LunarDate.fromSolarDate(
                *date.fromordinal(tomorrow).timetuple()[:3]
            )
            if int(next_day_lunar.month) == 1 and int(next_day_lunar.day) == 1:
                festival = "除夕"
        except ValueError:
            pass

        if lunar_day == 1:
            label = LUNAR_MONTH_NAMES[lunar_month]
        elif lunar_day == 10:
            label = "初十"
        elif lunar_day == 20:
            label = "二十"
        elif lunar_day == 30:
            label = "三十"
        else:
            prefix = LUNAR_DAY_PREFIX[(lunar_day - 1) // 10]
            number = LUNAR_DAY_NUMBERS[lunar_day % 10]
            label = f"{prefix}{number}"

        if is_leap:
            label = f"闰{label}"
        return label, festival, True

    def _holiday_info(self, solar_date: date) -> tuple[Optional[str], bool, bool]:
        if is_holiday is None or is_workday is None or get_holiday_detail is None:
            return None, False, False

        # chinesecalendar 同时负责判断法定休息日和周末调休上班日。
        holiday = bool(is_holiday(solar_date))
        adjusted_workday = bool(is_workday(solar_date) and solar_date.weekday() >= 5)
        detail = get_holiday_detail(solar_date)
        holiday_name = None

        if isinstance(detail, tuple) and len(detail) >= 2:
            raw_name = detail[1]
            if raw_name:
                holiday_name = str(getattr(raw_name, "name", raw_name))

        if holiday_name:
            holiday_name = self._translate_holiday_name(holiday_name)
        return holiday_name, holiday, adjusted_workday

    @staticmethod
    def _is_qingming(solar_date: date) -> bool:
        # 适用于 1900-2099 年的清明日期近似公式，常见年份为 4 月 4 日或 5 日。
        if solar_date.month != 4:
            return False
        day = int(solar_date.year * 0.2422 + 4.81) - int((solar_date.year - 1) / 4)
        return solar_date.day == day

    @staticmethod
    def _translate_holiday_name(name: str) -> str:
        # 第三方库可能返回枚举名或字符串，这里统一映射成用户可读的中文名称。
        mapping = {
            "new_years_day": "元旦",
            "spring_festival": "春节",
            "tomb_sweeping_day": "清明节",
            "labour_day": "劳动节",
            "dragon_boat_festival": "端午节",
            "mid_autumn_festival": "中秋节",
            "national_day": "国庆节",
        }
        normalized = name.lower().replace("holiday.", "").replace(" ", "_").replace("-", "_")
        return mapping.get(normalized, name)
