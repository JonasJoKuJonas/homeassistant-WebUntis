"""Demo platform that has two fake binary sensors."""
from __future__ import annotations

import copy
import datetime


from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import homeassistant.util.dt as dt_util


from homeassistant import core
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.components.calendar import CalendarEntity
from homeassistant.components.calendar import CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity_platform import DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


from .const import DOMAIN, ICON_CALENDER, NAME_CALENDER
from . import WebUntis, WebUntisEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [MyCalendar(server)]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class MyCalendar(WebUntisEntity, CalendarEntity):
    def __init__(self, server: WebUntis) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            server=server,
            type_name=NAME_CALENDER,
            icon=ICON_CALENDER,
            device_class=None,
        )
        self._name = NAME_CALENDER
        self.events = self._server.calendar_events
        self.events.sort(key=lambda e: (e.start, e.end))

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        if self.events:

            now = datetime.datetime.now()

            for event in self.events:
                if event.start_datetime_local >= now.astimezone():
                    return event
        else:
            return None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return self.events

    async def async_update(self) -> None:
        """Update status."""
        self.events = self._server.calendar_events
