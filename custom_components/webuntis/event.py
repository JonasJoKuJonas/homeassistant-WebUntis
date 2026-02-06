from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntisEntity
from .const import (
    DOMAIN,
    ICON_EVENT_LESSNON_CHANGE,
    NAME_EVENT_LESSON_CHANGE,
    ICON_EVENT_HOMEWORK,
    NAME_EVENT_HOMEWORK,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Example sensor based on a config entry."""
    server = hass.data[DOMAIN][config_entry.unique_id]
    entities = [LessonChangeEventEntity(server)]
    if server.timetable_source != "teacher":
        entities.append(HomeworkEventEntity(server))
    async_add_entities(
        entities,
        True,
    )


class BaseUntisEventEntity(WebUntisEntity, EventEntity):
    """Base class for WebUntis event entities."""

    def __init__(
        self,
        server,
        name: str,
        icon: str,
        event_types: list[str],
    ) -> None:
        """Initialize the base event entity."""
        super().__init__(server=server, name=name, icon=icon, device_class=None)
        self._server = server
        self._attr_event_types = event_types
        self.id = name

    @callback
    def _async_handle_event(self, event: str, data: dict) -> None:
        """Handle incoming event and update state."""
        self._trigger_event(event, data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register event listener with the server."""
        self._server.event_entity_listen(self._async_handle_event, self.id)

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True


class LessonChangeEventEntity(BaseUntisEventEntity):
    """Event entity for lesson changes."""

    def __init__(self, server) -> None:
        super().__init__(
            server=server,
            name=NAME_EVENT_LESSON_CHANGE,
            icon=ICON_EVENT_LESSNON_CHANGE,
            event_types=["lesson_change", "rooms", "teachers", "cancelled", "code", "lstext", "subject"],
        )


class HomeworkEventEntity(BaseUntisEventEntity):
    """Event entity for homework changes."""

    def __init__(self, server) -> None:
        super().__init__(
            server=server,
            name=NAME_EVENT_HOMEWORK,
            icon=ICON_EVENT_HOMEWORK,
            event_types=["homework"],
        )
