"""Constants for the Web Untis integration."""
DOMAIN = "webuntis"

CONFIG_ENTRY_VERSION = 9

DEFAULT_OPTIONS = {
    "calendar_long_name": True,
    "calendar_show_cancelled_lessons": False,
    "keep_loged_in": False,
    "filter_mode": "None",
    "filter_subjects": [],
    "generate_json": False,
    "exclude_data": [],
    "filter_description": [],
    "extended_timetable": False,
    "calendar_description": "JSON",
    "calendar_room": "long name",
}

ICON_STATUS = "mdi:school-outline"
ICON_NEXT_CLASS = "mdi:table-clock"
ICON_NEXT_LESSON_TO_WAKE_UP = "mdi:clock-start"
ICON_CALENDER = "mdi:school-outline"

NAME_STATUS = "Class"
NAME_NEXT_CLASS = "Next Class"
NAME_NEXT_LESSON_TO_WAKE_UP = "Next lesson to wake up"
NAME_CALENDER = " WebUntis Calender"

SCAN_INTERVAL = 60 * 5  # 5min

SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"

DAYS_TO_FUTURE = 30
