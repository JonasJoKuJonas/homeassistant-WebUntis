"""Constants for the Web Untis integration."""

DOMAIN = "webuntis"

CONFIG_ENTRY_VERSION = 17

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
    "calendar_description": "None",
    "calendar_room": "Room long name",
    "calendar_show_room_change": False,
    "notify_config": {},
    "invalid_subjects": False,
}

NOTIFY_OPTIONS = ["cancelled", "rooms", "lesson_change", "teachers", "code"]

TEMPLATE_OPTIONS = ["message_title", "message", "discord"]

ICON_STATUS = "mdi:school-outline"
ICON_NEXT_CLASS = "mdi:table-clock"
ICON_NEXT_LESSON_TO_WAKE_UP = "mdi:clock-start"
ICON_CALENDER = "mdi:school-outline"
ICON_TODAY_START = "mdi:calendar-start"
ICON_TODAY_END = "mdi:calendar-end"

NAME_STATUS = "Class"
NAME_NEXT_CLASS = "Next Class"
NAME_NEXT_LESSON_TO_WAKE_UP = "Next lesson to wake up"
NAME_CALENDER = "WebUntis Calender"
NAME_TODAY_START = "Today school start"
NAME_TODAY_END = "Today school end"

SCAN_INTERVAL = 5 * 60  # 5min

SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"

DAYS_TO_FUTURE = 30
