"""The Web Untis binary sensor platform."""
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity
from .const import DOMAIN, ICON_STATUS, NAME_STATUS


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Web Untis binary sensor platform."""
    server = hass.data[DOMAIN][config_entry.unique_id]

    # Create entities list.
    entities = [IsClassBinarySensor(server)]

    # Add binary sensor entities.
    async_add_entities(entities, True)


class IsClassBinarySensor(WebUntisEntity, BinarySensorEntity):
    """Representation of a Web Untis status binary sensor."""

    def __init__(self, server: WebUntis) -> None:
        """Initialize status binary sensor."""
        super().__init__(
            server=server,
            type_name=NAME_STATUS,
            icon=ICON_STATUS,
            device_class=None,
        )
        self._attr_is_on = False

    async def async_update(self) -> None:
        """Update status."""
        self._attr_is_on = self._server.is_class
