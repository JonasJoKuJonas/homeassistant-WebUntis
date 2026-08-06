"""Live Activities for the daily timetable."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv, issue_registry as ir, selector
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_call_later, async_track_point_in_time

from .const import (
    CONF_LIVE_ACTIVITIES,
    DOMAIN,
    ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP,
    ICON_SENSOR_TODAY_END,
    LIVE_ACTIVITY_TAG_SUFFIX,
)
from .utils.utils import async_notify, is_service
from .utils.web_untis import get_lesson_name

_LOGGER = logging.getLogger(__name__)

MAX_ACTIVITY_DURATION = timedelta(hours=8)

with (Path(__file__).parent / "translations" / "live_activity_strings.json").open(
    encoding="utf-8"
) as _f:
    _STRINGS: dict[str, dict[str, Any]] = json.load(_f)


# --------------------------------------------------------------------------
# Pure helpers
# --------------------------------------------------------------------------


def _language(hass: HomeAssistant) -> str:
    lang = (hass.config.language or "en").split("-")[0].lower()
    return lang if lang in _STRINGS else "en"


def _service_id_for_entity(hass: HomeAssistant, entity_id: str) -> str | None:
    """Return the legacy notify.mobile_app_<device> action for a notify.* entity."""
    object_id = entity_id.split(".", 1)[-1]
    if not object_id.startswith("mobile_app_"):
        object_id = f"mobile_app_{object_id}"
    service_id = f"notify.{object_id}"
    issue_id = f"live_activity_notify_missing_{entity_id}"

    if not is_service(hass, service_id):
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="live_activity_notify_missing",
            translation_placeholders={"entity_id": entity_id, "service_id": service_id},
        )
        return None

    ir.async_delete_issue(hass, DOMAIN, issue_id)
    return service_id


def _build_tag(username: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", username or "")
    return f"{sanitized}_{LIVE_ACTIVITY_TAG_SUFFIX}"[:64]


def _format_time(dt: datetime) -> str:
    return f"{dt.hour}:{dt.minute:02d}"


def _day_word(lang: str, target: date, today: date) -> str:
    delta = (target - today).days
    strings = _STRINGS[lang]
    if delta == 1:
        return strings["tomorrow"]
    if 1 < delta < 7:
        return strings["weekday"][target.weekday()]
    return f'{strings["on_prefix"]} {target.strftime("%d.%m.")}'


# --------------------------------------------------------------------------
# Timetable parsing
# --------------------------------------------------------------------------


def _build_day_blocks(server: Any, day: date) -> list[dict]:
    """Fetch, filter and merge today's lessons into blocks."""
    try:
        login_error = server.webuntis_login()
    except Exception as error:  # pylint: disable=broad-except
        login_error = error

    if login_error:
        _LOGGER.warning("Live Stundenplan: login failed for %s - %s", day, login_error)
        return []

    try:
        lessons = server.get_timetable(start=day, end=day, sort=True)
    except Exception as error:  # pylint: disable=broad-except
        _LOGGER.warning("Live Stundenplan: could not load timetable for %s - %s", day, error)
        return []
    finally:
        try:
            server.webuntis_logout()
        except Exception as error:  # pylint: disable=broad-except
            _LOGGER.debug("Live Stundenplan: logout after timetable fetch failed - %s", error)

    tolerance = timedelta(minutes=server.lesson_compacting_tolerance)

    items = []
    for lesson in lessons:
        if not server.check_lesson(lesson):
            continue
        try:
            room = lesson.rooms[0].name if lesson.rooms else ""
        except (IndexError, AttributeError):
            room = ""
        items.append(
            {
                "start": lesson.start.astimezone(),
                "end": lesson.end.astimezone(),
                "lsnumber": getattr(lesson, "lsnumber", None),
                "subject": get_lesson_name(server, lesson),
                "room": room,
            }
        )
    items.sort(key=lambda i: i["start"])

    blocks: list[dict] = []
    for item in items:
        if (
            blocks
            and item["start"] >= blocks[-1]["end"]
            and item["start"] - blocks[-1]["end"] <= tolerance
            and item["lsnumber"] == blocks[-1]["lsnumber"]
        ):
            blocks[-1]["end"] = item["end"]
            continue
        blocks.append(dict(item))

    return blocks


def _build_events(blocks: list[dict], start_offset: int, end_offset: int) -> list[dict]:
    """Turn today's blocks into a timeline of (time, phase, block) events."""
    if not blocks:
        return []

    events: list[dict] = []
    first, last = blocks[0], blocks[-1]

    events.append(
        {
            "time": first["start"] - timedelta(minutes=start_offset),
            "phase": "schulbeginn",
            "block": first,
            "restart": False,
        }
    )

    for i, block in enumerate(blocks):
        events.append({"time": block["start"], "phase": "unterricht", "block": block, "restart": False})
        if i + 1 < len(blocks):
            following = blocks[i + 1]
            if following["start"] > block["end"]:
                events.append(
                    {"time": block["end"], "phase": "pause", "block": following, "restart": False}
                )

    events.append({"time": last["end"], "phase": "schulende", "block": None, "restart": False})
    events.append(
        {
            "time": last["end"] + timedelta(minutes=end_offset),
            "phase": "clear",
            "block": None,
            "restart": False,
        }
    )

    events.sort(key=lambda e: e["time"])
    return events


def _flag_restart(events: list[dict]) -> None:
    """Flag the pause closest to the midpoint for a restart."""
    if not events:
        return
    span = events[-1]["time"] - events[0]["time"]
    if span <= MAX_ACTIVITY_DURATION:
        return

    midpoint = events[0]["time"] + span / 2
    pauses = [e for e in events if e["phase"] == "pause"]
    if not pauses:
        _LOGGER.warning(
            "Live Stundenplan: school day is longer than 8h and has no break to "
            "restart the Live Activity during - it may end early once iOS's "
            "limit is hit."
        )
        return

    closest = min(pauses, key=lambda e: abs((e["time"] - midpoint).total_seconds()))
    closest["restart"] = True


def _current_phase(events: list[dict], now: datetime) -> dict | None:
    """Most recent event that is due, i.e. what should be showing right now."""
    past = [e for e in events if e["time"] <= now]
    if not past:
        return None
    return max(past, key=lambda e: e["time"])


def _signature(event: dict) -> tuple:
    """Identifies the displayed content, so unchanged phases are not resent."""
    phase = event["phase"]
    block = event["block"]
    if phase in ("schulbeginn", "unterricht"):
        return (phase, block["start"].isoformat(), block["end"].isoformat(), block["subject"], block["room"])
    if phase == "pause":
        return (phase, block["subject"], block["room"])
    return (phase,)


def _build_payload(
    event: dict, lang: str, next_school_day: datetime | None
) -> tuple[str, str, dict]:
    """Build the (title, message, extra_data) triple for one phase."""
    phase = event["phase"]
    block = event["block"]
    strings = _STRINGS[lang]
    lesson_text = f'{block["subject"]} - R{block["room"]}' if block else ""

    when: datetime | None = None

    if phase == "schulbeginn":
        title = strings["school_start_title"]
        message = "\n".join([strings["school_start_begin"].format(time=_format_time(block["start"])), lesson_text])
        icon, color, silent = ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP, "#2196F3", False
    elif phase == "unterricht":
        title = lesson_text
        message = " "
        icon, color, silent, when = "mdi:school", "orange", True, block["end"]
    elif phase == "pause":
        title = strings["break_title"]
        message = strings["break_next"].format(lesson=lesson_text)
        icon, color, silent = "mdi:school-outline", "lightgreen", False
    elif phase == "schulende":
        if next_school_day:
            day_word = _day_word(lang, next_school_day.date(), date.today())
            time_str = _format_time(next_school_day)
        else:
            day_word = time_str = "?"
        title = strings["school_end_title"]
        message = strings["school_end_next"].format(day=day_word, time=time_str)
        icon, color, silent = ICON_SENSOR_TODAY_END, "white", True
    else:
        return "", "", {}

    extra = {
        "notification_icon": icon,
        "notification_icon_color": color,
        "silent": silent,
    }
    if when is not None:
        extra["chronometer"] = True
        extra["when"] = int(when.timestamp())

    return title, message, extra


# --------------------------------------------------------------------------
# Test send
# --------------------------------------------------------------------------

TEST_TAG_SUFFIX = "live_stundenplan_test"
TEST_ACTIVITY_DURATION = timedelta(seconds=60)


def _build_test_tag(entity_id: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9_-]", "_", entity_id or "")
    return f"{sanitized}_{TEST_TAG_SUFFIX}"[:64]


async def async_send_test(hass: HomeAssistant, entity_id: str, lang: str) -> bool:
    """Send one real, standalone test Live Activity and self-clear shortly after."""
    service_id = _service_id_for_entity(hass, entity_id)
    if service_id is None:
        return False
    tag = _build_test_tag(entity_id)
    strings = _STRINGS[lang]
    now = datetime.now().astimezone()

    success = await async_notify(
        hass,
        service_id,
        {
            "title": strings["test_title"],
            "message": strings["test_message"],
            "data": {
                "tag": tag,
                "live_update": True,
                "silent": False,
                "chronometer": True,
                "when": int((now + TEST_ACTIVITY_DURATION).timestamp()),
                "notification_icon": "mdi:bell-ring-outline",
                "notification_icon_color": "#2196F3",
            },
        },
    )

    if success:

        @callback
        def _clear(_now: datetime) -> None:
            hass.async_create_task(
                async_notify(hass, service_id, {"message": "clear_notification", "data": {"tag": tag}})
            )

        async_call_later(hass, TEST_ACTIVITY_DURATION.total_seconds(), _clear)

    return success


# --------------------------------------------------------------------------
# Send scheduling
# --------------------------------------------------------------------------


class LiveActivityManager:

    def __init__(self, hass: HomeAssistant, server: Any) -> None:
        self.hass = hass
        self.server = server
        self._unsub_dispatcher = None
        self._unsub_timers: list = []
        self._last_sent: dict[str, tuple] = {}
        self._restarted: set[tuple[str, str]] = set()
        self._cleared_dates: dict[str, date] = {}

    def start(self) -> None:
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, self.server.signal_name, self._handle_update
        )
        self._handle_update()

    def stop(self) -> None:
        for unsub in self._unsub_timers:
            unsub()
        self._unsub_timers = []
        if self._unsub_dispatcher:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None

    @callback
    def _handle_update(self, *_args: Any) -> None:
        self.hass.async_create_task(self._async_sync())

    @callback
    def _handle_timer(self, *_args: Any) -> None:
        self.hass.async_create_task(self._async_sync())

    async def _async_sync(self) -> None:
        targets = self.server.live_activities
        if not targets:
            return

        for unsub in self._unsub_timers:
            unsub()
        self._unsub_timers = []

        today = date.today()
        blocks = await self.hass.async_add_executor_job(_build_day_blocks, self.server, today)
        lang = _language(self.hass)
        now = datetime.now().astimezone()

        next_time: datetime | None = None
        for target in targets.values():
            events = _build_events(blocks, target.get("start_offset", 10), target.get("end_offset", 10))
            _flag_restart(events)

            future = [e["time"] for e in events if e["time"] > now]
            if future:
                soonest = min(future)
                next_time = soonest if next_time is None else min(next_time, soonest)

            await self._sync_target(target, events, now, lang, today)

        self._prune(today)

        if next_time is not None:
            self._unsub_timers.append(
                async_track_point_in_time(self.hass, self._handle_timer, next_time)
            )

    async def _sync_target(
        self, target: dict, events: list[dict], now: datetime, lang: str, today: date
    ) -> None:
        entity_id = target["entity_id"]
        service_id = _service_id_for_entity(self.hass, entity_id)
        if service_id is None:
            return
        tag = _build_tag(self.server.username)

        current = _current_phase(events, now)
        if current is None:
            return

        if current["phase"] == "clear":
            if self._cleared_dates.get(entity_id) != today:
                await async_notify(
                    self.hass, service_id, {"message": "clear_notification", "data": {"tag": tag}}
                )
                self._cleared_dates[entity_id] = today
                self._last_sent.pop(entity_id, None)
            return

        signature = _signature(current)
        if self._last_sent.get(entity_id) == signature:
            return

        if current["phase"] == "pause" and current["restart"]:
            restart_key = (entity_id, current["block"]["start"].isoformat())
            if restart_key not in self._restarted:
                await async_notify(
                    self.hass, service_id, {"message": "clear_notification", "data": {"tag": tag}}
                )
                self._restarted.add(restart_key)

        next_school_day = (
            self.server.next_lesson_to_wake_up if current["phase"] == "schulende" else None
        )
        title, message, extra = _build_payload(current, lang, next_school_day)

        await async_notify(
            self.hass,
            service_id,
            {
                "title": title,
                "message": message,
                "data": {"tag": tag, "live_update": True, **extra},
            },
        )
        self._last_sent[entity_id] = signature

    def _prune(self, today: date) -> None:
        """Drop old bookkeeping so long uptimes don't grow these forever."""
        cutoff = (today - timedelta(days=2)).isoformat()
        self._cleared_dates = {
            entity_id: cleared_on
            for entity_id, cleared_on in self._cleared_dates.items()
            if cleared_on.isoformat() >= cutoff
        }
        self._restarted = {
            (entity_id, start_iso) for entity_id, start_iso in self._restarted if start_iso >= cutoff
        }


# --------------------------------------------------------------------------
# Options flow
# --------------------------------------------------------------------------


class LiveActivityOptionsFlowMixin:
    """Mixed into OptionsFlowHandler; expects self._config_entry/self.hass/self.save."""

    async def list_live_activities(
        self,
        step_id: str,
        multible: bool = False,
        required: bool = True,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        activities = {
            entity_id: activity["name"]
            for entity_id, activity in self._config_entry.options[CONF_LIVE_ACTIVITIES].items()
        }

        select = cv.multi_select if multible else vol.In
        required_marker = vol.Required if required else vol.Optional

        return self.async_show_form(
            step_id=step_id,
            errors=errors or {},
            data_schema=vol.Schema({required_marker("services"): select(activities)}),
        )

    async def async_step_live_activities_menu(
        self,
        user_input: dict[str, str] | None = None,  # pylint: disable=unused-argument
    ) -> FlowResult:
        """Manage the live_activities_menu options."""
        if not self._config_entry.options[CONF_LIVE_ACTIVITIES]:
            options = ["edit_live_activity"]
        else:
            options = [
                "edit_live_activity",
                "edit_live_activity_select",
                "remove_live_activity",
                "test_live_activity",
            ]
        return self.async_show_menu(step_id="live_activities_menu", menu_options=options)

    async def async_step_test_live_activity(
        self,
        user_input: dict[str, str] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Send a real test Live Activity right away."""
        if user_input is None:
            return await self.list_live_activities(
                "test_live_activity", multible=True, required=False, errors=errors
            )

        lang = _language(self.hass)
        for entity_id in user_input.get("services", {}):
            if not await async_send_test(self.hass, entity_id, lang):
                return await self.async_step_test_live_activity(
                    None, errors={"base": "notification_invalid"}
                )

        return await self.save({})

    async def async_step_edit_live_activity_select(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        if user_input is None:
            return await self.list_live_activities("edit_live_activity_select")
        return await self.async_step_edit_live_activity(edit=user_input["services"])

    async def async_step_remove_live_activity(
        self,
        user_input: dict[str, str] | None = None,
    ) -> FlowResult:
        if user_input is None:
            return await self.list_live_activities("remove_live_activity", multible=True)

        live_activities = self._config_entry.options[CONF_LIVE_ACTIVITIES]
        for key in user_input["services"]:
            live_activities.pop(key, None)
            ir.async_delete_issue(self.hass, DOMAIN, f"live_activity_notify_missing_{key}")
        return await self.save(
            {
                CONF_LIVE_ACTIVITIES: live_activities,
                "toggle": not self._config_entry.options.get("toggle"),
            }
        )

    async def async_step_edit_live_activity(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
        edit: str | None = None,
    ) -> FlowResult:
        options: dict[str, Any] = {}
        if edit:
            options = self._config_entry.options[CONF_LIVE_ACTIVITIES].get(edit, {})

        if user_input is not None:
            if "name" not in user_input:
                user_input["name"] = user_input["entity_id"]

            live_activities = self._config_entry.options[CONF_LIVE_ACTIVITIES]
            live_activities[user_input["entity_id"]] = user_input
            return await self.save(
                {
                    CONF_LIVE_ACTIVITIES: live_activities,
                    "toggle": not self._config_entry.options.get("toggle"),
                }
            )

        schema = {
            vol.Optional(
                "name",
                description={"suggested_value": options.get("name")},
            ): selector.TextSelector(),
            vol.Required(
                "platform",
                description={"suggested_value": options.get("platform")},
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["ios"],
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="live_activity_platform",
                )
            ),
            vol.Required(
                "entity_id",
                description={"suggested_value": options.get("entity_id")},
            ): selector.EntitySelector(selector.EntitySelectorConfig(domain="notify")),
            vol.Optional(
                "start_offset",
                default=10,
                description={"suggested_value": options.get("start_offset", 10)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
                )
            ),
            vol.Optional(
                "end_offset",
                default=10,
                description={"suggested_value": options.get("end_offset", 10)},
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=0, step=1, unit_of_measurement="min", mode=selector.NumberSelectorMode.BOX
                )
            ),
        }

        return self.async_show_form(
            step_id="edit_live_activity",
            data_schema=vol.Schema(schema),
            errors=errors,
        )
