"""Services for WebUntis integration."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .utils.web_untis import get_schoolyear

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for WebUntis integration."""

    if hass.services.has_service(DOMAIN, "get_timetable"):
        return

    async def async_call_webuntis_service(service_call: ServiceCall) -> None:
        """Call correct WebUntis service."""

        entry_id = await async_extract_config_entry_ids(hass, service_call)
        config_entry = hass.config_entries.async_get_entry(list(entry_id)[0])
        webuntis_object = hass.data[DOMAIN][config_entry.unique_id]

        data = service_call.data

        start_date = datetime.strptime(data["start"], "%Y-%m-%d")
        end_date = datetime.strptime(data["end"], "%Y-%m-%d")

        if end_date < start_date:
            raise HomeAssistantError(f"Start date has to be bevor end date")

        if not get_schoolyear(webuntis_object.school_year, date=start_date.date()):
            raise HomeAssistantError(f"Start date is not in any schoolyear")

        await hass.async_add_executor_job(webuntis_object.webuntis_login)

        if service_call.service == "get_timetable":
            lesson_list = await hass.async_add_executor_job(
                webuntis_object._get_events_in_timerange,
                start_date,
                end_date,
                data["apply_filter"],
                data["show_cancelled"],
                data["compact_result"],
            )
            result = {"lessons": lesson_list}

        elif service_call.service == "count_lessons":
            result = await hass.async_add_executor_job(
                webuntis_object._count_lessons,
                start_date,
                end_date,
                data["apply_filter"],
                data["count_cancelled"],
            )

        await hass.async_add_executor_job(webuntis_object.webuntis_logout)

        return result

    hass.services.async_register(
        DOMAIN,
        "get_timetable",
        async_call_webuntis_service,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "count_lessons",
        async_call_webuntis_service,
        supports_response=SupportsResponse.ONLY,
    )
