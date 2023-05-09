"""The Web Untis integration."""
from __future__ import annotations

import logging
from asyncio.log import logger
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any
import json

# pylint: disable=import-self
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval

from homeassistant.components.calendar import CalendarEvent
import homeassistant.util.dt as dt_util

import webuntis

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    SIGNAL_NAME_PREFIX,
    DAYS_TO_FUTURE,
)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.CALENDAR]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up WebUntis from a config entry."""
    domain_data = hass.data.setdefault(DOMAIN, {})

    # Create and store server instance.
    assert entry.unique_id
    unique_id = entry.unique_id
    _LOGGER.debug(
        "Creating server instance for '%s' (%s)",
        entry.data["username"],
        entry.data["school"],
    )

    server = WebUntis(hass, unique_id, entry)
    domain_data[unique_id] = server
    await server.async_update()
    server.start_periodic_update()

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register update listener.
    entry.async_on_unload(entry.add_update_listener(async_update_entry))

    return True


async def async_update_entry(hass, entry):
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    _LOGGER.debug("Migrating from version %s", config_entry.version)

    if config_entry.version == 1:
        new_options = {**config_entry.options}

        new_options["calendar_long_name"] = True

        config_entry.version = 2
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 2:
        new_options = {**config_entry.options}
        new_options["calendar_show_cancelled_lessons"] = False
        config_entry.version = 3
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 3:
        new_options = {**config_entry.options}
        new_options["keep_loged_in"] = False
        config_entry.version = 4
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 4:
        new_options = {**config_entry.options}
        new_options["filter_mode"] = "None"
        new_options["filter_subjects"] = []
        config_entry.version = 5
        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 5:
        new_options = {**config_entry.options}
        new_options["exclude_data"] = []
        new_options["generate_json"] = False
        config_entry.version = 6

        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 6:
        new_options = {**config_entry.options}
        new_options["filter_description"] = []
        new_options["extended_timetable"] = False
        config_entry.version = 7

        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 7:
        new_options = {**config_entry.options}
        new_options["calendar_description"] = "JSON"
        config_entry.version = 8

        hass.config_entries.async_update_entry(config_entry, options=new_options)

    if config_entry.version == 8:
        new_options = {**config_entry.options}
        new_options["calendar_room"] = "Room long name"
        config_entry.version = 9

        hass.config_entries.async_update_entry(config_entry, options=new_options)

    _LOGGER.info("Migration to version %s successful", config_entry.version)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unique_id = config_entry.unique_id
    server = hass.data[DOMAIN][unique_id]

    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    # Clean up.
    server.stop_periodic_update()
    hass.data[DOMAIN].pop(unique_id)

    return unload_ok


class WebUntis:
    """Representation of a WebUntis client."""

    def __init__(
        self,
        hass: HomeAssistant,
        unique_id: str,
        config: Mapping[str, Any],
    ) -> None:
        """Initialize client instance."""
        self._hass = hass
        self._config = config

        # Server data
        self.unique_id = unique_id
        self.server = config.data["server"]
        self.school = config.data["school"]
        self.username = config.data["username"]
        self.password = config.data["password"]
        self.timetable_source = config.data["timetable_source"]
        self.timetable_source_id = config.data["timetable_source_id"]

        self.calendar_long_name = config.options["calendar_long_name"]
        self.calendar_show_cancelled_lessons = config.options[
            "calendar_show_cancelled_lessons"
        ]
        self.calendar_description = config.options["calendar_description"]
        self.calendar_room = config.options["calendar_room"]

        self.keep_loged_in = config.options["keep_loged_in"]

        self.filter_mode = config.options["filter_mode"]  # Blacklist, Whitelist, None
        self.filter_subjects = config.options["filter_subjects"]

        self.exclude_data = config.options["exclude_data"]
        self.filter_description = config.options["filter_description"]
        self.generate_json = config.options["generate_json"]

        self.extended_timetable = config.options["extended_timetable"]

        # pylint: disable=maybe-no-member
        self.session = webuntis.Session(
            username=self.username,
            password=self.password,
            server=self.server,
            useragent="foo",
            school=self.school,
        )
        self._loged_in = False
        self._last_status_request_failed = False

        # Data provided by 3rd party library
        self.is_class = None
        self.next_class = None
        self.next_class_json = None
        self.next_lesson_to_wake_up = None
        self.calendar_events = []
        self.next_day_json = None

        self.subjects = []

        # Dispatcher signal name
        self.signal_name = f"{SIGNAL_NAME_PREFIX}_{self.unique_id}"

        # Callback for stopping periodic update.
        self._stop_periodic_update: CALLBACK_TYPE | None = None

    def start_periodic_update(self) -> None:
        """Start periodic execution of update method."""
        self._stop_periodic_update = async_track_time_interval(
            self._hass, self.async_update, timedelta(seconds=SCAN_INTERVAL)
        )

    def stop_periodic_update(self) -> None:
        """Stop periodic execution of update method."""
        if self._stop_periodic_update:
            self._stop_periodic_update()

    # pylint: disable=unused-argument
    async def async_update(self, now: datetime | None = None) -> None:
        """Get server data from 3rd party library and update properties."""

        await self._async_status_request()

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self.signal_name)

    async def _async_status_request(self) -> None:
        """Request status and update properties."""

        if self._loged_in:
            # Check if there is a session id.
            if "jsessionid" not in self.session.config:
                _LOGGER.debug("No session id found")
                self._loged_in = False
            else:
                # Check if session id is still valid.
                try:
                    await self._hass.async_add_executor_job(self.session.schoolyears)
                except webuntis.errors.NotLoggedInError:
                    _LOGGER.debug("Session invalid")
                    self._loged_in = False

        if not self._loged_in:
            _LOGGER.debug("logging in")

            try:
                await self._hass.async_add_executor_job(self.session.login)
                _LOGGER.debug("Login successful")
                self._loged_in = True
            except OSError as error:
                # Login error, set all properties to unknown.
                self.is_class = None
                self.next_class = None
                self.next_class_json = None
                self.next_lesson_to_wake_up = None
                self.calendar_events = []
                self.next_day_json = None

                # Inform user once about failed update if necessary.
                if not self._last_status_request_failed:
                    _LOGGER.warning(
                        "Login to WebUntis '%s@%s' failed - OSError: %s",
                        self.school,
                        self.username,
                        error,
                    )
                self._last_status_request_failed = True
                return
            except error as error:
                _LOGGER.error(
                    "Login to WebUntis '%s@%s' failed - ERROR: %s",
                    self.school,
                    self.username,
                    error,
                )
                self._last_status_request_failed = True
                return

        _LOGGER.debug("updating data")

        try:
            self.subjects = await self._hass.async_add_executor_job(
                self.session.subjects
            )
        except OSError as error:
            self.subjects = []

            _LOGGER.warning(
                "Updating the propertie subjects of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        try:
            self.is_class = await self._hass.async_add_executor_job(self._is_class)
        except OSError as error:
            self.is_class = None

            _LOGGER.warning(
                "Updating the propertie is_class of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        try:
            self.next_class = await self._hass.async_add_executor_job(self._next_class)
        except OSError as error:
            self.next_class = None

            _LOGGER.warning(
                "Updating the propertie next_class of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        try:
            self.next_lesson_to_wake_up = await self._hass.async_add_executor_job(
                self._next_lesson_to_wake_up
            )
        except OSError as error:
            self.next_lesson_to_wake_up = None

            _LOGGER.warning(
                "Updating the propertie next_lesson_to_wake_up of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        try:
            self.next_day_json = await self._hass.async_add_executor_job(
                self._next_day_json
            )
        except OSError as error:
            self.next_day_json = None

            _LOGGER.warning(
                "Updating the propertie next_day_json of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        try:
            self.calendar_events = await self._hass.async_add_executor_job(
                self._get_events
            )
        except OSError as error:
            self.calendar_events = []

            _LOGGER.warning(
                "Updating the propertie calendar_events of '%s@%s' failed - OSError: %s",
                self.school,
                self.username,
                error,
            )

        if not self.keep_loged_in:
            await self._hass.async_add_executor_job(self.session.logout)
            _LOGGER.debug("Logout successful")
            self._loged_in = False

    def get_timetable_object(self):
        """return the object to request the timetable"""
        if self.timetable_source == "student":
            source = self.session.get_student(
                self.timetable_source_id[1], self.timetable_source_id[0]
            )
        elif self.timetable_source == "klasse":
            klassen = self.session.klassen()
            # pylint: disable=maybe-no-member
            source = klassen.filter(name=self.timetable_source_id)[0]
        elif self.timetable_source == "teacher":
            source = self.session.get_teacher(
                self.timetable_source_id[1], self.timetable_source_id[0]
            )
        elif self.timetable_source == "subject":
            pass
        elif self.timetable_source == "room":
            pass

        return {self.timetable_source: source}

    def get_timetable(self, start, end):
        """Get the timetable for the given time period"""
        timetable_object = self.get_timetable_object()

        if self.extended_timetable:
            return self.session.timetable_extended(
                start=start, end=end, **timetable_object
            )
        return self.session.timetable(start=start, end=end, **timetable_object)

    def _is_class(self):
        """return if is class"""
        today = date.today()

        table = self.get_timetable(start=today, end=today)

        now = datetime.now()

        for lesson in table:
            # pylint: disable=maybe-no-member
            if lesson.start < now < lesson.end and self.check_lesson(lesson):
                return True
        return False

    def _next_class(self):
        """returns time of next class."""
        today = date.today()
        in_x_days = today + timedelta(days=DAYS_TO_FUTURE)

        # pylint: disable=maybe-no-member
        table = self.get_timetable(start=today, end=in_x_days)

        now = datetime.now()

        lesson_list = []
        for lesson in table:
            if lesson.start > now and self.check_lesson(lesson):
                lesson_list.append(lesson)

        lesson_list.sort(key=lambda e: (e.start))

        try:
            lesson = lesson_list[0]
        except IndexError:
            _LOGGER.warning(
                "Updating the propertie _next_class of '%s@%s' failed - No lesson in the next %s days",
                self.school,
                self.username,
                DAYS_TO_FUTURE,
            )
            return None

        self.next_class_json = self.get_lesson_json(lesson)

        return lesson.start.astimezone()

    def _next_lesson_to_wake_up(self):
        """returns time of the next lesson to weak up."""
        today = date.today()
        now = datetime.now()
        in_x_days = today + timedelta(days=DAYS_TO_FUTURE)

        # pylint: disable=maybe-no-member
        table = self.get_timetable(start=today, end=in_x_days)

        time_list = []
        for lesson in table:
            if self.check_lesson(lesson):
                time_list.append(lesson.start)

        day = now
        time_list_new = []
        for time in sorted(time_list):
            if time < day:
                day = now.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) + timedelta(days=1)
                continue
            else:
                time_list_new.append(time)

        try:
            return sorted(time_list_new)[0].astimezone()
        except IndexError:
            _LOGGER.warning(
                "Updating the propertie _next_lesson_to_wake_up of '%s@%s' failed - No lesson in the next %s days",
                self.school,
                self.username,
                DAYS_TO_FUTURE,
            )
            return None

    def _next_day_json(self):
        if self.next_lesson_to_wake_up is None:
            return None
        day = self.next_lesson_to_wake_up

        table = self.get_timetable(start=day, end=day)

        lessons = []
        for lesson in table:
            if self.check_lesson(lesson):
                lessons.append(str(self.get_lesson_json(lesson)))

        json_str = "[" + ", ".join(lessons) + "]"

        return json_str

    def _get_events(self):
        today = date.today()
        in_x_days = today + timedelta(days=DAYS_TO_FUTURE)

        table = self.get_timetable(start=today, end=in_x_days)

        event_list = []

        for lesson in table:
            if self.check_lesson(
                lesson, ignor_cancelled=self.calendar_show_cancelled_lessons
            ):
                try:
                    event = {}
                    if self.calendar_long_name:
                        event["summary"] = lesson.subjects[0].long_name
                    else:
                        event["summary"] = lesson.subjects[0].name

                    if lesson.code == "cancelled":
                        event["summary"] = "Cancelled: " + event["summary"]

                    event["start"] = lesson.start.astimezone()
                    event["end"] = lesson.end.astimezone()
                    if self.calendar_description == "JSON":
                        event["description"] = self.get_lesson_json(lesson, True)
                    elif self.calendar_description == "Lesson Info":
                        event["description"] = str(lesson.substText)

                    # add Room as location
                    try:
                        if lesson.rooms and not self.calendar_room == "None":
                            if self.calendar_room == "Room long name":
                                event["location"] = lesson.rooms[0].long_name
                            elif self.calendar_room == "Room short name":
                                event["location"] = lesson.rooms[0].name
                            elif self.calendar_room == "Room short-long name":
                                event[
                                    "location"
                                ] = f"{lesson.rooms[0].name} - {lesson.rooms[0].long_name}"
                    except IndexError:
                        # server does not return rooms
                        pass

                    event_list.append(CalendarEvent(**event))
                except OSError as error:
                    _LOGGER.warning(
                        "Updating of a calendar_event of '%s@%s' failed - OSError: %s",
                        self.school,
                        self.username,
                        error,
                    )

        return event_list

    def check_lesson(self, lesson, ignor_cancelled=False) -> bool:
        """Checks if a lesson is taking place"""
        if lesson.code == "cancelled" and not ignor_cancelled:
            return False

        if not lesson.subjects:
            return False

        for filter_description in self.filter_description:
            if (
                filter_description in lesson.lstext  # Vertretungstext
                or filter_description in lesson.substText  # Informationen zur Stunde
            ):
                return False

        if self.filter_mode == "Blacklist":
            if any(subject.name in self.filter_subjects for subject in lesson.subjects):
                return False
        if self.filter_mode == "Whitelist" and self.filter_subjects:
            if not any(
                subject.name in self.filter_subjects for subject in lesson.subjects
            ):
                return False

        return True

    # pylint: disable=bare-except
    def get_lesson_json(self, lesson, force=False) -> str:
        """returns info about lesson in json"""
        if (not self.generate_json) and (not force):
            return "JSON data is disabled - activate it in the options"
        dic = {}
        dic["start"] = str(lesson.start.astimezone())
        dic["end"] = str(lesson.end.astimezone())
        try:
            dic["id"] = int(lesson.id)
        except:
            pass
        try:
            dic["code"] = str(lesson.code)
        except:
            pass
        try:
            dic["type"] = str(lesson.type)
        except:
            pass
        try:
            dic["subjects"] = [
                {"name": str(subject.name), "long_name": str(subject.long_name)}
                for subject in lesson.subjects
            ]
        except:
            pass

        if self.extended_timetable:
            try:
                dic["lstext"] = str(lesson.lstext)
            except:
                pass
            try:
                dic["substText"] = str(lesson.substText)
            except:
                pass

        try:
            dic["rooms"] = [
                {"name": str(room.name), "long_name": str(room.long_name)}
                for room in lesson.rooms
            ]
        except:
            pass
        try:
            dic["klassen"] = [
                {"name": str(klasse.name), "long_name": str(klasse.long_name)}
                for klasse in lesson.klassen
            ]
        except:
            pass
        try:
            dic["original_rooms"] = [
                {"name": str(room.name), "long_name": str(room.long_name)}
                for room in lesson.original_rooms
            ]
        except:
            pass

        if "teachers" not in self.exclude_data:
            try:
                dic["teachers"] = [
                    {"name": str(teacher.name), "long_name": str(teacher.long_name)}
                    for teacher in lesson.teachers
                ]
            except OSError as error:
                if "no right for getTeachers()" in str(error):
                    self.exclude_data_("teachers")
                    _LOGGER.info(
                        "No rights for getTeachers() for '%s@%s', getTeachers is now on blacklist",
                        self.school,
                        self.username,
                    )
            except:
                pass

            try:
                dic["original_teachers"] = [
                    {"name": str(teacher.name), "long_name": str(teacher.long_name)}
                    for teacher in lesson.original_teachers
                ]
            except:
                pass

        return str(json.dumps(dic))

    def exclude_data_(self, data):
        """adds data to exclude_data list"""

        new_options = {**self._config.options}
        new_options["exclude_data"] = [*new_options["exclude_data"], data]

        self._hass.config_entries.async_update_entry(self._config, options=new_options)
        self.exclude_data.append(data)


class WebUntisEntity(Entity):
    """Representation of a Web Untis base entity."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        server: WebUntis,
        type_name: str,
        icon: str,
        device_class: str | None,
    ) -> None:
        """Initialize base entity."""
        self._server = server
        self._attr_name = type_name
        self._attr_icon = icon
        self._attr_unique_id = f"{self._server.unique_id}-{type_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._server.unique_id)},
            manufacturer="Web Untis",
            model=f"{self._server.username}@{self._server.school}",
            name=self._server.username,
        )
        self._attr_device_class = device_class
        self._extra_state_attributes = None
        self._disconnect_dispatcher: CALLBACK_TYPE | None = None

    async def async_update(self) -> None:
        """Fetch data from the server."""
        raise NotImplementedError()

    async def async_added_to_hass(self) -> None:
        """Connect dispatcher to signal from server."""
        self._disconnect_dispatcher = async_dispatcher_connect(
            self.hass, self._server.signal_name, self._update_callback
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect dispatcher before removal."""
        if self._disconnect_dispatcher:
            self._disconnect_dispatcher()

    @callback
    def _update_callback(self) -> None:
        """Triggers update of properties after receiving signal from server."""
        self.async_schedule_update_ha_state(force_refresh=True)
