from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntisEntity
from .const import DOMAIN, ICON_EVENT_ENTITY, NAME_EVENT_ENTITY


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Example sensor based on a config entry."""
    server = hass.data[DOMAIN][config_entry.unique_id]
    async_add_entities([LessonChangeEventEntity(server)], True)


class LessonChangeEventEntity(WebUntisEntity, EventEntity):
    """Representation of a Web Untis Event entity."""

    _attr_event_types = [
        "homework",
        "code",
        "rooms",
        "teachers",
        "cancelled",
        "lesson_change",
    ]
    _attr_translation_key = "lesson_change_event"

    def __init__(self, server) -> None:
        """Set up the instance."""

        super().__init__(
            server=server,
            type_name=NAME_EVENT_ENTITY,
            icon=ICON_EVENT_ENTITY,
            device_class=None,
        )

        self._server = server

    @callback
    def _async_handle_event(self, event: str, data: dict) -> None:
        """Handle the demo button event."""
        self._trigger_event(event, data)
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks with your device API/library."""
        self._server.listen_on_lesson_change(self._async_handle_event)

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True
