"""Constants for the Web Untis integration."""

DOMAIN = "webuntis"

CONFIG_ENTRY_VERSION = 18

DEFAULT_OPTIONS = {
    "lesson_long_name": True,
    "calendar_show_cancelled_lessons": False,
    "keep_loged_in": False,
    "filter_mode": "None",
    "filter_subjects": [],
    "generate_json": False,
    "exclude_data": [],
    "filter_description": [],
    "calendar_description": "none",
    "calendar_room": "Room long name",
    "calendar_show_room_change": False,
    "notify_config": {},
    "invalid_subjects": False,
}

NOTIFY_OPTIONS = ["homework", "cancelled", "rooms", "lesson_change", "teachers", "code"]

TEMPLATE_OPTIONS = ["message_title", "message", "discord", "telegram"]


ICON_SENSOR_NEXT_CLASS = "mdi:table-clock"
ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP = "mdi:clock-start"
ICON_SENSOR_TODAY_START = "mdi:calendar-start"
ICON_SENSOR_TODAY_END = "mdi:calendar-end"
ICON_CALENDER = "mdi:school-outline"
ICON_CALENDER_HOMEWORK = "mdi:home-edit"
ICON_CALENDER_EXAM = "mdi:pen"
ICON_EVENT_LESSNON_CHANGE = "mdi:calendar-clock"
ICON_EVENT_HOMEWORK = "mdi:home-edit"

NAME_SENSOR_NEXT_CLASS = "next_class"
NAME_SENSOR_NEXT_LESSON_TO_WAKE_UP = "next_lesson_to_wake_up"
NAME_SENSOR_TODAY_START = "today_school_start"
NAME_SENSOR_TODAY_END = "today_school_end"
NAME_CALENDER = "calender"
NAME_CALENDER_HOMEWORK = "homework"
NAME_CALENDER_EXAM = "exam"
NAME_EVENT_LESSNON_CHANGE = "lesson_change"
NAME_EVENT_HOMEWORK = "new_homework"


SCAN_INTERVAL = 10 * 60  # 10min

SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"

DAYS_TO_FUTURE = 30

# Homework
DAYS_TO_CHECK = 30
