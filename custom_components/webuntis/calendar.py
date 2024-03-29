"""Demo platform that has two fake binary sensors."""
from __future__ import annotations

import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity
from .const import DOMAIN, ICON_CALENDER, NAME_CALENDER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [UntisCalendar(server)]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class UntisCalendar(WebUntisEntity, CalendarEntity):
    """Representation of a Web Untis Calendar sensor."""

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
        self._event = None

    @property
    def name(self) -> str:
        """Return the name of the entity."""
        return self._name

    @property
    def event(self) -> CalendarEvent:
        """Return the next upcoming event."""
        return self._event

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime.datetime,
        end_date: datetime.datetime,
    ) -> list[CalendarEvent]:
        """Return calendar events within a datetime range."""
        return [
            event
            for event in self.events
            if event.start >= start_date and event.end <= end_date
        ]

    async def async_update(self) -> None:
        """Update status."""
        self.events = self._server.calendar_events

        if self.events:
            self.events.sort(key=lambda e: (e.end))
            now = datetime.datetime.now()

            for event in self.events:
                if event.end_datetime_local.astimezone() > now.astimezone():
                    self._event = event
                    break
        else:
            self._event = None
