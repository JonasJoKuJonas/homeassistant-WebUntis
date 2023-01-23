"""Config flow for webuntisnew integration."""
from __future__ import annotations

import logging

# from msilib.schema import Error
from typing import Any

import socket

import datetime
from urllib.parse import urlparse
import requests

import webuntis

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import DOMAIN, CONFIG_ENTRY_VERSION, DEFAULT_OPTIONS

_LOGGER = logging.getLogger(__name__)


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if user_input["timetable_source"] in ["student", "teacher"]:
        for char in [",", " "]:
            split = user_input["timetable_source_id"].split(char)
            if len(split) == 2:
                break
        if len(split) == 2:
            user_input["timetable_source_id"] = [
                split.strip(" ").capitalize() for split in split
            ]
        else:
            raise NameSplitError

    try:
        socket.gethostbyname(user_input["server"])
    except Exception as exc:
        raise CannotConnect from exc

    try:
        # pylint: disable=maybe-no-member
        session = webuntis.Session(
            server=user_input["server"],
            school=user_input["school"],
            username=user_input["username"],
            password=user_input["password"],
            useragent="foo",
        )
        await hass.async_add_executor_job(session.login)
    except webuntis.errors.BadCredentialsError as ext:
        raise BadCredentials from ext
    except requests.exceptions.ConnectionError as exc:
        raise CannotConnect from exc
    except webuntis.errors.RemoteError as exc:  # pylint: disable=no-member
        raise SchoolNotFound from exc
    except Exception as exc:
        raise InvalidAuth from exc

    timetable_source_id = user_input["timetable_source_id"]
    timetable_source = user_input["timetable_source"]

    if timetable_source == "student":
        try:
            source = await hass.async_add_executor_job(
                session.get_student, timetable_source_id[1], timetable_source_id[0]
            )
        except Exception as exc:
            raise StudentNotFound from exc
    elif timetable_source == "klasse":
        klassen = await hass.async_add_executor_job(session.klassen)
        try:
            source = klassen.filter(name=timetable_source_id)[0]
        except Exception as exc:
            raise ClassNotFound from exc
    elif timetable_source == "teacher":
        try:
            source = await hass.async_add_executor_job(
                session.get_teacher, timetable_source_id[1], timetable_source_id[0]
            )
        except Exception as exc:
            raise TeacherNotFound from exc
    elif timetable_source == "subject":
        pass
    elif timetable_source == "room":
        pass

    try:
        await hass.async_add_executor_job(
            test_timetable, session, timetable_source, source
        )
    except Exception as exc:
        raise NoRightsForTimetable from exc

    return {"title": user_input["username"]}


def test_timetable(session, timetable_source, source):
    """test if timetable is allowed to be fetched"""
    today = datetime.date.today()
    session.timetable(start=today, end=today, **{timetable_source: source})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for webuntisnew."""

    VERSION = CONFIG_ENTRY_VERSION

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            # return self.async_step_optional()
            return self._show_form_user()

        await self.async_set_unique_id(
            # pylint: disable=consider-using-f-string
            "{username}@{timetable_source_id}@{school}".format(**user_input)
            .lower()
            .replace(" ", "-")
        )
        self._abort_if_unique_id_configured()

        errors = {}

        if not user_input["server"].startswith(("http://", "https://")):
            user_input["server"] = "https://" + user_input["server"]
        user_input["server"] = urlparse(user_input["server"]).netloc

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except BadCredentials:
            errors["base"] = "bad_credentials"
        except SchoolNotFound:
            errors["base"] = "school_not_found"
        except NameSplitError:
            errors["base"] = "name_split_error"
        except StudentNotFound:
            errors["base"] = "student_not_found"
        except TeacherNotFound:
            errors["base"] = "teacher_not_found"
        except ClassNotFound:
            errors["base"] = "class_not_found"
        except NoRightsForTimetable:
            errors["base"] = "no_rights_for_timetable"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(
                title=info["title"],
                data=user_input,
                options=DEFAULT_OPTIONS,
            )

        timetable_source_id = (
            ", ".join(user_input["timetable_source_id"])
            if isinstance(user_input["timetable_source_id"], list)
            else user_input["timetable_source_id"]
        )

        user_input["timetable_source_id"] = timetable_source_id

        return self._show_form_user(user_input, errors)

    def _show_form_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is None:
            user_input = {}

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("server", default=user_input.get("server", "")): str,
                    vol.Required("school", default=user_input.get("school", "")): str,
                    vol.Required(
                        "username", default=user_input.get("username", "")
                    ): str,
                    vol.Required(
                        "password", default=user_input.get("password", "")
                    ): str,
                    vol.Required(
                        "timetable_source", default=user_input.get("timetable_source")
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "student",
                                "klasse",
                                "teacher",
                            ],  # "subject", "room"
                            mode="dropdown",
                        )
                    ),
                    vol.Required(
                        "timetable_source_id",
                        default=user_input.get("timetable_source_id", ""),
                    ): str,
                }
            ),
            errors=errors,
        )


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the option flow for WebUntis."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "calendar_long_name",
                        default=self.config_entry.options.get("calendar_long_name"),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "calendar_show_cancelled_lessons",
                        default=self.config_entry.options.get(
                            "calendar_show_cancelled_lessons"
                        ),
                    ): selector.BooleanSelector(),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BadCredentials(HomeAssistantError):
    """Error to indicate there are bad credentials."""


class SchoolNotFound(HomeAssistantError):
    """Error to indicate the school is not found."""


class NameSplitError(HomeAssistantError):
    """Error to indicate the name format is wrong."""


class StudentNotFound(HomeAssistantError):
    """Error to indicate there is no student with this name."""


class TeacherNotFound(HomeAssistantError):
    """Error to indicate there is no teacher with this name."""


class ClassNotFound(HomeAssistantError):
    """Error to indicate there is no class with this name."""


class NoRightsForTimetable(HomeAssistantError):
    """Error to indicate there is no right for timetable."""
