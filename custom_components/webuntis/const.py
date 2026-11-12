"""Constants for the Web Untis integration."""

DOMAIN = "webuntis"

CONFIG_ENTRY_VERSION = 24

CONF_LIVE_ACTIVITIES = "live_activities"
CONF_FRONTEND_CARD_REGISTERED = "frontend_card_registered"

FRONTEND_CARD_URL_PATH = "/webuntis_files/webuntis-homework-card.js"

DEFAULT_OPTIONS = {
    "lesson_long_name": True,
    "calendar_show_cancelled_lessons": False,
    "keep_loged_in": False,
    "filter_mode": "None",
    "filter_subjects": [],
    "filter_klassen": [],
    "generate_json": False,
    "exclude_data": [],
    "filter_description": [],
    "lesson_compacting_tolerance": 0,
    "lesson_compacting_parallel": False,
    "calendar_description": "none",
    "calendar_room": "Room long name",
    "calendar_show_room_change": False,
    "homework_display": "span",
    "notify_config": {},
    "invalid_subjects": False,
    "exclude_filter_comparison": False,
    "live_activities": {},
    "messages": False,
    "message_attachments": False,
    "message_attachments_unread": False,
}

LIVE_ACTIVITY_TAG_SUFFIX = "live_timetable"

NOTIFY_OPTIONS = [
    "homework",
    "cancelled",
    "rooms",
    "teachers",
    "code",
    "lstext",
    "subject",
    "info",
    "replacement",
    "message",
]

TEMPLATE_OPTIONS = ["message_title", "message", "discord", "telegram"]


ICON_SENSOR_NEXT_CLASS = "mdi:table-clock"
ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP = "mdi:clock-start"
ICON_SENSOR_TODAY_START = "mdi:calendar-start"
ICON_SENSOR_TODAY_END = "mdi:calendar-end"
ICON_CALENDAR = "mdi:school-outline"
ICON_CALENDAR_HOMEWORK = "mdi:home-edit"
ICON_CALENDAR_EXAM = "mdi:pen"
ICON_EVENT_LESSNON_CHANGE = "mdi:calendar-clock"
ICON_EVENT_HOMEWORK = "mdi:home-edit"
ICON_SENSOR_HOMEWORK_LIST = "mdi:notebook-check-outline"
ICON_SENSOR_MESSAGES = "mdi:email-outline"
ICON_EVENT_MESSAGE = "mdi:email-alert-outline"

NAME_SENSOR_NEXT_CLASS = "next_class"
NAME_SENSOR_NEXT_LESSON_TO_WAKE_UP = "next_lesson_to_wake_up"
NAME_SENSOR_TODAY_START = "today_school_start"
NAME_SENSOR_TODAY_END = "today_school_end"
NAME_SENSOR_HOMEWORK_LIST = "homework_list"
NAME_SENSOR_MESSAGES = "messages"
NAME_CALENDAR = "calendar"
NAME_CALENDAR_HOMEWORK = "homework"
NAME_CALENDAR_EXAM = "exam"
NAME_EVENT_LESSON_CHANGE = "lesson_change"
NAME_EVENT_HOMEWORK = "new_homework"
NAME_EVENT_MESSAGE = "new_message"


SCAN_INTERVAL = 10 * 60  # 10min

SIGNAL_NAME_PREFIX = f"signal_{DOMAIN}"

DAYS_TO_FUTURE = 30

# Homework
DAYS_TO_CHECK = 30
# Days before the due date a homework entry is grouped as "due soon"
HOMEWORK_DUE_SOON_DAYS = 3

# Messages ("Mitteilungen")
# Number of messages exposed as sensor attribute
MESSAGES_MAX_ATTRIBUTE = 10
# Maximum characters of the message text in attributes, events and notifications
# (state attributes are limited to 16 KB in total)
MESSAGES_MAX_TEXT_LENGTH = 1000
# Size budget for the messages attribute in bytes (HA limit is 16 KB)
MESSAGES_MAX_ATTRIBUTE_BYTES = 12000
# Texts are shortened down to this length before older messages are dropped
MESSAGES_MIN_TEXT_LENGTH = 200
# Attachment link tokens: validity and when they are renewed
MESSAGES_ATTACHMENT_URL_EXPIRY = 7 * 24 * 60 * 60  # 7 days
MESSAGES_ATTACHMENT_URL_RENEW = 24 * 60 * 60  # renew when less than 1 day is left
# Name of the single link shown for attachments that have not been loaded yet
MESSAGES_ATTACHMENTS_PLACEHOLDER = "Open attachments"
MESSAGES_ATTACHMENT_VIEW_URL = (
    "/api/webuntis/{entry_id}/messages/{message_id}/attachments"
)
CONF_ATTACHMENT_VIEW_REGISTERED = "message_attachment_view_registered"
