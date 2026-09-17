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
    ICON_SENSOR_HOMEWORK_LIST,
    ICON_SENSOR_NEXT_CLASS,
    ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP,
    ICON_SENSOR_TODAY_END,
    ICON_SENSOR_TODAY_START,
    NAME_SENSOR_HOMEWORK_LIST,
    NAME_SENSOR_NEXT_CLASS,
    NAME_SENSOR_NEXT_LESSON_TO_WAKE_UP,
    NAME_SENSOR_TODAY_END,
    NAME_SENSOR_TODAY_START,
)
from .utils.homework import build_homework_list


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
        WebUntisToayStart(server),
        WebUntisToayEnd(server),
        WebUntisHomeworkListSensor(server),
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
        name: str,
        icon: str,
        device_class: Optional[str] = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server, name, icon, device_class)
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
            name=NAME_SENSOR_NEXT_CLASS,
            icon=ICON_SENSOR_NEXT_CLASS,
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

    unit: Optional[str] = None
    device_class: Optional[str] = "timestamp"

    def __init__(self, server: WebUntis) -> None:
        """Initialize next lesson to wake up sensor."""
        super().__init__(
            server=server,
            name=NAME_SENSOR_NEXT_LESSON_TO_WAKE_UP,
            icon=ICON_SENSOR_NEXT_LESSON_TO_WAKE_UP,
            device_class=self.device_class,
        )
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Update next lesson to wake up."""
        self._attr_native_value = self._server.next_lesson_to_wake_up
        self._attr_extra_state_attributes = {"day": self._server.next_day_json}


class WebUntisToayStart(WebUntisSensorEntity):
    """Representation of a Web Untis Today start sensor."""

    unit: Optional[str] = None
    device_class: Optional[str] = "timestamp"

    def __init__(self, server: WebUntis) -> None:
        """Initialize sensor."""
        super().__init__(
            server=server,
            name=NAME_SENSOR_TODAY_START,
            icon=ICON_SENSOR_TODAY_START,
            device_class=self.device_class,
        )
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Update sensor data."""
        self._attr_native_value = self._server.today[0]
        self._attr_extra_state_attributes = {"day": self._server.day_json}


class WebUntisToayEnd(WebUntisSensorEntity):
    """Representation of a Web Untis Today end sensor."""

    unit: Optional[str] = None
    device_class: Optional[str] = "timestamp"

    def __init__(self, server: WebUntis) -> None:
        """Initialize sensor."""
        super().__init__(
            server=server,
            name=NAME_SENSOR_TODAY_END,
            icon=ICON_SENSOR_TODAY_END,
            device_class=self.device_class,
        )
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Update sensor data."""
        self._attr_native_value = self._server.today[-1]


class WebUntisHomeworkListSensor(WebUntisSensorEntity):
    """Representation of a Web Untis Homework List sensor.

    Exposes the full homework list, grouped like the WebUntis "Hausaufgaben"
    view ("due_soon", "open", "overdue", "completed"), as an attribute so it
    can be rendered by a dashboard card.
    """

    unit: Optional[str] = None
    device_class: Optional[str] = None

    def __init__(self, server: WebUntis) -> None:
        """Initialize the Homework List sensor."""
        super().__init__(
            server=server,
            name=NAME_SENSOR_HOMEWORK_LIST,
            icon=ICON_SENSOR_HOMEWORK_LIST,
            device_class=self.device_class,
        )
        self._attr_extra_state_attributes = {"homeworks": []}

    async def async_update(self) -> None:
        """Update the homework list sensor."""
        homeworks = build_homework_list(self._server.homework_list)
        self._attr_native_value = sum(
            1 for homework in homeworks if not homework["completed"]
        )
        self._attr_extra_state_attributes = {"homeworks": homeworks}
