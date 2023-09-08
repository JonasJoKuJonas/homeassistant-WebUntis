"""Services for WebUntis integration."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Fritz integration."""

    if hass.services.has_service(DOMAIN, "get_timetable"):
        return

    async def async_call_fritz_service(service_call: ServiceCall) -> None:
        """Call correct Fritz service."""

        entry_id = await async_extract_config_entry_ids(hass, service_call)
        config_entry = hass.config_entries.async_get_entry(list(entry_id)[0])

        webuntis_object = hass.data[DOMAIN][config_entry.unique_id]

        data = service_call.data

        start_date = datetime.strptime(data["start"], "%Y-%m-%d")

        end_date = datetime.strptime(data["end"], "%Y-%m-%d")

        timetable = await hass.async_add_executor_job(
            webuntis_object._get_events_timerange, start_date, end_date
        )

        timetable = {"test": "ds"}

        return timetable

    hass.services.async_register(
        DOMAIN,
        "get_timetable",
        async_call_fritz_service,
        supports_response=SupportsResponse.ONLY,
    )
