"""The Web Untis sensor platform."""
from __future__ import annotations

import asyncio
from typing import Optional

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import WebUntis, WebUntisEntity
from .const import DOMAIN, ICON_NEXT_CLASS, ICON_NEXT_LESSON_TO_WAKE_UP, NAME_NEXT_CLASS, SCAN_INTERVAL, \
    NAME_NEXT_LESSON_TO_WAKE_UP, COLOR_NEXT_CLASS, COLOR_NEXT_LESSON_TO_WAKE_UP


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
    async_add_entities(entities)

    # Start schedule monitor if notify is enabled.
    if config_entry.options.get("notify", True):
        notify_service = hass.data[DOMAIN]["notify_service"]
        notify_enabled = config_entry.options.get("notify", True)
        hass.loop.create_task(async_monitor_schedule(server, notify_service, notify_enabled))


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
            color: Optional[str] = None,
    ) -> None:
        """Initialize sensor base entity."""
        super().__init__(server, type_name, icon, device_class)
        self._attr_native_unit_of_measurement = self.unit
        self._attr_extra_state_attributes = {COLOR_NEXT_CLASS: color} if color else {}
        self.device_class = device_class or self.device_class  # Set default device_class if not provided

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return True


class WebUntisNextClassSensor(WebUntisSensorEntity):
    """Representation of a Web Untis next class sensor."""

    unit: Optional[str] = None
    device_class: Optional[str] = "timestamp"

    def __init__(self, server: WebUntis, color: Optional[str] = None) -> None:  # Neue Option für die Farbe
        """Initialize next class sensor."""
        super().__init__(
            server=server,
            type_name=NAME_NEXT_CLASS,
            icon=ICON_NEXT_CLASS,
            device_class=self.device_class,
            color=color,  # Neue Zeile für die Farbe
        )

    @property
    def available(self) -> bool:
        """Return sensor availability."""
        return bool(self._server.next_class)

    async def async_update(self) -> None:
        """Update next class."""
        self._attr_native_value = self._server.next_class
        self._attr_extra_state_attributes = {
            "lesson": self._server.next_class_json,
            COLOR_NEXT_CLASS: self._attr_extra_state_attributes.get(COLOR_NEXT_CLASS),  # Neue Zeile für die Farbe
        }


class WebUntisNextLessonToWakeUpSensor(WebUntisSensorEntity):
    """Representation of a Web Untis next lesson to wake up sensor."""

    def __init__(self, server: WebUntis, color: Optional[str] = None) -> None:  # Neue Option für die Farbe
        """Initialize next lesson to wake up sensor."""
        super().__init__(
            server=server,
            type_name=NAME_NEXT_LESSON_TO_WAKE_UP,
            icon=ICON_NEXT_LESSON_TO_WAKE_UP,
            device_class="timestamp",
            color=color,  # Neue Zeile für die Farbe
        )
        self._attr_extra_state_attributes = {}

    async def async_update(self) -> None:
        """Update next lesson to wake up."""
        self._attr_native_value = self._server.next_lesson_to_wake_up
        self._attr_extra_state_attributes = {
            "day": self._server.next_day_json,
            COLOR_NEXT_LESSON_TO_WAKE_UP: self._attr_extra_state_attributes.get(COLOR_NEXT_LESSON_TO_WAKE_UP),
            # Neue Zeile für die Farbe
        }


async def async_monitor_schedule(server: WebUntis, notify_service: str, notify_enabled: bool) -> None:
    """Monitor schedule for changes and send notifications if enabled."""
    last_schedule = None

    while True:
        # Get current schedule.
        schedule = server.get_schedule()

        # Check if schedule has changed.
        if schedule != last_schedule and notify_enabled:
            # Send notification.
            message = "Your schedule has been updated:\n\n" + schedule
            await server.hass.services.async_call(
                "notify", notify_service, {"message": message}
            )

            # Update last schedule.
            last_schedule = schedule

        # Wait for next update.
        await asyncio.sleep(SCAN_INTERVAL)