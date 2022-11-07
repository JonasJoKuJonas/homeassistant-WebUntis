"""Config flow for webuntisnew integration."""
from __future__ import annotations

import logging

# from msilib.schema import Error
from typing import Any

import webuntis
import socket
import requests
import datetime
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("server"): str,
        vol.Required("school"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Required("timetable_source"): selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=["student", "klasse", "teacher"],  # "subject", "room"
                mode="dropdown",
            )
        ),
        vol.Required("timetable_source_id"): str,
    }
)


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
    except webuntis.errors.RemoteError as exc:
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
        source = klassen.filter(name=timetable_source_id)[0]
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

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )
        await self.async_set_unique_id(
            "{username}@{school}".format(**user_input).lower().replace(" ", "-")
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
        except NoRightsForTimetable:
            errors["base"] = "no_rights_for_timetable"

        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        timetable_source_id = (
            ", ".join(user_input["timetable_source_id"])
            if isinstance(user_input["timetable_source_id"], list)
            else user_input["timetable_source_id"]
        )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("server", default=user_input["server"]): str,
                    vol.Required("school", default=user_input["school"]): str,
                    vol.Required("username", default=user_input["username"]): str,
                    vol.Required("password", default=user_input["password"]): str,
                    vol.Required(
                        "timetable_source", default=user_input["timetable_source"]
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
                        "timetable_source_id", default=timetable_source_id
                    ): str,
                }
            ),
            errors=errors,
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


class NoRightsForTimetable(HomeAssistantError):
    """Error to indicate there is no right for timetable."""
