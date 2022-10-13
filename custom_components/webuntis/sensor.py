"""The Web Untis sensor platform."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity
from .const import (
    DOMAIN,
    ICON_NEXT_CLASS,
    NAME_NEXT_CLASS,
    ICON_FIRST_CLASS,
    NAME_FIRST_CLASS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [WebUntisNextClassSensor(server), WebUntisFirstClassSensor(server)]

    # Add sensor entities.
    async_add_entities(entities, True)


class WebUntisSensorEntity(WebUntisEntity, SensorEntity):
    """Representation of a Web Untis sensor base entity."""

    def __init__(
        self,
        server: WebUntis,
        type_name: str,
        icon: str,
        unit: str | None,
        device_class: str | None = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server, type_name, icon, device_class)
        self._attr_native_unit_of_measurement = unit

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True


class WebUntisNextClassSensor(WebUntisSensorEntity):
    """Representation of a Web Untis next class sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize next class sensor."""
        super().__init__(
            server=server,
            type_name=NAME_NEXT_CLASS,
            icon=ICON_NEXT_CLASS,
            unit=None,
            device_class="timestamp",
        )

    async def async_update(self) -> None:
        """Update next class."""
        self._attr_native_value = self._server.next_class


class WebUntisFirstClassSensor(WebUntisSensorEntity):
    """Representation of a Web Untis first class sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize first class sensor."""
        super().__init__(
            server=server,
            type_name=NAME_FIRST_CLASS,
            icon=ICON_FIRST_CLASS,
            unit=None,
            device_class="timestamp",
        )

    async def async_update(self) -> None:
        """Update first class."""
        self._attr_native_value = self._server.first_class
