"""Services for WebUntis integration."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.service import async_extract_config_entry_ids

from .const import DOMAIN
from .utils.rest_timetable import (
    RestTimetableError,
    fetch_rest_timetable,
    get_rest_lessons,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for WebUntis integration."""

    if hass.services.has_service(DOMAIN, "get_timetable"):
        return

    service_locks: dict[str, asyncio.Lock] = {}

    async def async_call_webuntis_service(
        service_call: ServiceCall,
    ) -> ServiceResponse | None:
        """Call correct WebUntis service."""

        entry_id = await async_extract_config_entry_ids(service_call)
        config_entry = hass.config_entries.async_get_entry(next(iter(entry_id)))
        assert config_entry is not None
        assert config_entry.unique_id is not None
        webuntis_object = hass.data[DOMAIN][config_entry.unique_id]

        data = service_call.data

        if "start" in data and "end" in data:
            start_date = datetime.strptime(data["start"], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )
            end_date = datetime.strptime(data["end"], "%Y-%m-%d").replace(
                tzinfo=timezone.utc
            )

            if end_date < start_date:
                raise HomeAssistantError("Start date has to be before end date")

        # Service calls share the integration's WebUntis session. Run them one at a
        # time per account and only log out if this call did the login, otherwise
        # parallel calls (and the regular polling) lose their session midway.
        result: ServiceResponse | None = None
        lock = service_locks.setdefault(config_entry.unique_id, asyncio.Lock())
        async with lock:
            was_logged_in = bool(getattr(webuntis_object, "_loged_in", False))
            await hass.async_add_executor_job(webuntis_object.webuntis_login)
            try:
                if service_call.service == "get_timetable":
                    lesson_list = await hass.async_add_executor_job(
                        webuntis_object._get_events_in_timerange,
                        start_date,
                        end_date,
                        data["apply_filter"],
                        data["show_cancelled"],
                        data["compact_result"],
                        data.get("compact_tolerance_minutes", 0),
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

                elif service_call.service == "get_schoolyears":
                    result = await hass.async_add_executor_job(
                        webuntis_object._get_schoolyears
                    )

                elif service_call.service == "get_rest_timetable":
                    try:
                        if data.get("raw", False):
                            result = await hass.async_add_executor_job(
                                fetch_rest_timetable,
                                webuntis_object.session,
                                start_date.date(),
                                end_date.date(),
                            )
                        else:
                            lessons = await hass.async_add_executor_job(
                                get_rest_lessons,
                                webuntis_object.session,
                                start_date.date(),
                                end_date.date(),
                            )
                            result = {"lessons": lessons}
                    except RestTimetableError as err:
                        raise HomeAssistantError(str(err)) from err
            finally:
                if not was_logged_in:
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
    hass.services.async_register(
        DOMAIN,
        "get_schoolyears",
        async_call_webuntis_service,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        "get_rest_timetable",
        async_call_webuntis_service,
        supports_response=SupportsResponse.ONLY,
    )
