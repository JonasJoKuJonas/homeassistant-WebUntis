"""The Web Untis integration."""
from __future__ import annotations
from asyncio.log import logger

from collections.abc import Mapping
from datetime import datetime, timedelta, date
import logging
from typing import Any

import webuntis

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform


from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.dispatcher import (
    async_dispatcher_connect,
    async_dispatcher_send,
)
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SCAN_INTERVAL, SIGNAL_NAME_PREFIX

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

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

    server = WebUntis(hass, unique_id, entry.data)
    domain_data[unique_id] = server
    await server.async_update()
    server.start_periodic_update()

    # Set up platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

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
        self, hass: HomeAssistant, unique_id: str, config_data: Mapping[str, Any]
    ) -> None:
        """Initialize client instance."""
        self._hass = hass

        # Server data
        self.unique_id = unique_id
        self.server = config_data["server"]
        self.school = config_data["school"]
        self.username = config_data["username"]
        self.password = config_data["password"]
        self.timetable_source = config_data["timetable_source"]
        self.timetable_source_id = config_data["timetable_source_id"]

        self.session = webuntis.Session(
            username=self.username,
            password=self.password,
            server=self.server,
            useragent="foo",
            school=self.school,
        )

        self.version = None
        self.protocol_version = None
        self.latency_time = None
        self.players_online = None
        self.players_max = None
        self.players_list: list[str] | None = None
        self.motd = None

        self._last_status_request_failed = False

        # Data provided by 3rd party library
        self.is_class = None
        self.next_class = None

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

    async def async_update(self, now: datetime | None = None) -> None:
        """Get server data from 3rd party library and update properties."""

        await self._async_status_request()

        # Notify sensors about new data.
        async_dispatcher_send(self._hass, self.signal_name)

    async def _async_status_request(self) -> None:
        """Request status and update properties."""
        self.is_class = False

        try:
            await self._hass.async_add_executor_job(self.session.login)
        except OSError as error:
            # Login error, set all properties to unknown.
            self.is_class = None
            self.next_class = None

            self.session = webuntis.Session(
                username=self.username,
                password=self.password,
                server=self.server,
                useragent="foo",
                school=self.school,
            )

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

        try:
            self.is_class = await self._hass.async_add_executor_job(self._is_class)
        except OSError as error:
            self.is_class = None

            _LOGGER.warning(
                "Updating the propertie next_class of '%s@%s' failed - OSError: %s",
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
        await self._hass.async_add_executor_job(self.session.logout)

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
            pass
        elif self.timetable_source == "subject":
            pass
        elif self.timetable_source == "room":
            pass

        return {self.timetable_source: source}

    def _is_class(self):
        """return if is class"""
        today = date.today()
        timetable_object = self.get_timetable_object()

        table = self.session.timetable(start=today, end=today, **timetable_object)

        now = datetime.now()

        for lesson in table:
            # pylint: disable=maybe-no-member
            if lesson.start < now < lesson.end and lesson.code != "cancelled":
                return True
        return False

    def _next_class(self):
        """returns time of next class."""
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        friday = monday + timedelta(days=4)
        timetable_object = self.get_timetable_object()

        # pylint: disable=maybe-no-member
        table = self.session.timetable(
            start=monday, end=friday, **timetable_object
        ).to_table()

        now = datetime.now()
        last_time = None

        for time, row in table:
            for date_, cell in row:
                for i in cell:
                    if i.start > now and i.code != "cancelled":
                        return (
                            i.start.astimezone()
                            if last_time is None
                            else last_time.astimezone()
                        )
                    last_time = i.start


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
