from __future__ import annotations

import datetime

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity  # pylint: disable=no-name-in-module
from .const import (
    DOMAIN,
    ICON_CALENDAR,
    ICON_CALENDAR_HOMEWORK,
    NAME_CALENDAR,
    NAME_CALENDAR_HOMEWORK,
    ICON_CALENDAR_EXAM,
    NAME_CALENDAR_EXAM,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis calendar platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    entities = [UntisCalendar(server)]

    if server.timetable_source != "teacher":
        entities.append(HomeworkCalendar(server))
        entities.append(ExamCalendar(server))

    # Add calendar entities.
    async_add_entities(entities, True)


class BaseUntisCalendar(WebUntisEntity, CalendarEntity):
    """Base class for WebUntis calendar entities."""

    def __init__(self, server: WebUntis, name: str, icon: str) -> None:
        """Initialize base calendar entity."""
        super().__init__(
            server=server,
            name=name,
            icon=icon,
            device_class=None,
        )
        self.events = self._get_events
        self._event = None

    def _get_events(self):
        return []

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
        events_in_range = []
        # Use the timezone of the start_date (or Home Assistant timezone)
        timezone = start_date.tzinfo or datetime.timezone.utc

        for event in self.events:
            # Convert event.start and event.end to datetime if they are date objects
            if isinstance(event.start, datetime.date) and not isinstance(
                event.start, datetime.datetime
            ):
                event_start = datetime.datetime.combine(
                    event.start, datetime.time.min
                ).replace(tzinfo=timezone)
            else:
                event_start = event.start

            if isinstance(event.end, datetime.date) and not isinstance(
                event.end, datetime.datetime
            ):
                event_end = datetime.datetime.combine(
                    event.end, datetime.time.min
                ).replace(tzinfo=timezone)
            else:
                event_end = event.end

            # Ensure event_start and event_end are timezone-aware
            if event_start.tzinfo is None:
                event_start = event_start.replace(tzinfo=timezone)
            if event_end.tzinfo is None:
                event_end = event_end.replace(tzinfo=timezone)

            # Now compare the event start and end with the given range
            if event_start >= start_date and event_end <= end_date:
                events_in_range.append(event)

        return events_in_range

    async def async_update(self) -> None:
        """Update status."""
        self.events = self._get_events()

        if self.events:
            self.events.sort(key=lambda e: (e.end))
            now = datetime.datetime.now()

            for event in self.events:
                if event.end_datetime_local.astimezone() > now.astimezone():
                    self._event = event
                    break
        else:
            self._event = None


class UntisCalendar(BaseUntisCalendar):
    """Representation of a Web Untis Calendar sensor."""

    _attr_name = None

    def __init__(self, server: WebUntis) -> None:
        """Initialize the Untis Calendar."""
        super().__init__(server=server, name=NAME_CALENDAR, icon=ICON_CALENDAR)

    def _get_events(self):
        return self._server.calendar_events


class HomeworkCalendar(BaseUntisCalendar):
    """Representation of a Web Untis Homework Calendar sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize the Homework Calendar."""
        super().__init__(
            server=server, name=NAME_CALENDAR_HOMEWORK, icon=ICON_CALENDAR_HOMEWORK
        )

    def _get_events(self):

        return self._server.calendar_homework


class ExamCalendar(BaseUntisCalendar):
    """Representation of a Web Untis Exams Calendar sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize the Exams Calendar."""
        super().__init__(
            server=server, name=NAME_CALENDAR_EXAM, icon=ICON_CALENDAR_EXAM
        )

    def _get_events(self):

        return self._server.calendar_exams
