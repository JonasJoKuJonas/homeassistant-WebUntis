"""The Web Untis sensor platform."""
from __future__ import annotations

from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity
from .const import (
    DOMAIN,
    ICON_NEXT_CLASS,
    NAME_NEXT_CLASS,
    ICON_NEXT_LESSON_TO_WAKE_UP,
    NAME_NEXT_LESSON_TO_WAKE_UP,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [
        WebUntisNextClassSensor(server),
        WebUntisNextLessonToWakeUpSensor(server),
    ]

    # Add sensor entities.
    async_add_entities(entities, True)
    

class WebUntisSensorEntity(WebUntisEntity, SensorEntity):
    """Representation of a Web Untis sensor base entity."""

    unit: Optional[str] = None
    device_class: Optional[str] = None

    def __init__(
        self,
        server: WebUntis,
        type_name: str,
        icon: str,
        device_class: Optional[str] = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server, type_name, icon, device_class)
        self._attr_native_unit_of_measurement = self.unit

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True


class WebUntisNextClassSensor(WebUntisSensorEntity):
    """Representation of a Web Untis next class sensor."""

    unit: Optional[str] = None
    device_class: Optional[str] = "timestamp"

    def __init__(self, server: WebUntis) -> None:
        """Initialize next class sensor."""
        super().__init__(
            server=server,
            type_name=NAME_NEXT_CLASS,
            icon=ICON_NEXT_CLASS,
            device_class=self.device_class,
        )
        
    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return bool(self._server.next_class)

    async def async_update(self) -> None:
        """Update next class."""
        self._attr_native_value = self._server.next_class
        self._attr_extra_state_attributes = {"lesson": self._server.next_class_json}


class WebUntisNextLessonToWakeUpSensor(WebUntisSensorEntity):
    """Representation of a Web Untis next lesson to wake up sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize next lesson to wake up sensor."""
        super().__init__(
            server=server,
            type_name=NAME_NEXT_LESSON_TO_WAKE_UP,
            icon=ICON_NEXT_LESSON_TO_WAKE_UP,
            unit=None,
            device_class="timestamp",
        )
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Update next lesson to wake up."""
        self._attr_native_value = self._server.next_lesson_to_wake_up
        self._attr_extra_state_attributes = {"day": self._server.next_day_json}
