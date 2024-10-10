"""Config flow for webuntisnew integration."""

from __future__ import annotations

import datetime
import logging
import socket
from typing import Any

import requests
import voluptuous as vol

# pylint: disable=maybe-no-member
import webuntis

from urllib.parse import urlparse

from homeassistant import config_entries
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector

from .const import (
    CONFIG_ENTRY_VERSION,
    DEFAULT_OPTIONS,
    DOMAIN,
    NOTIFY_OPTIONS,
    TEMPLATE_OPTIONS,
)
from .notify import get_notification_data
from .utils.errors import *
from .utils.utils import async_notify, is_service
from .utils.web_untis import get_schoolyear, get_timetable_object

# import webuntis.session


_LOGGER = logging.getLogger(__name__)


async def validate_login(
    hass: HomeAssistant, credentials: dict[str, Any]
) -> dict[str, Any]:

    errors = {}

    if not credentials["server"].startswith(("http://", "https://")):
        try:
            socket.gethostbyname(credentials["server"])
        except Exception as exc:
            _LOGGER.error("Cannot resolve hostname(%s): %s", credentials["server"], exc)
            errors["server"] = "cannot_connect"
            return errors

        credentials["server"] = "https://" + credentials["server"]
        credentials["server"] = urlparse(credentials["server"]).netloc

    try:
        session = webuntis.Session(
            server=credentials["server"],
            school=credentials["school"],
            username=credentials["username"],
            password=credentials["password"],
            useragent="home-assistant",
        )
        await hass.async_add_executor_job(session.login)
    except webuntis.errors.BadCredentialsError:
        errors["username"] = "bad_credentials"
    except requests.exceptions.ConnectionError as exc:
        _LOGGER.error("webuntis.Session connection error: %s", exc)
        errors["server"] = "cannot_connect"
    except webuntis.errors.RemoteError as exc:  # pylint: disable=no-member
        errors["school"] = "school_not_found"
    except Exception as exc:
        _LOGGER.error("webuntis.Session unknown error: %s", exc)
        errors["base"] = "unknown"

    return errors, session


def test_timetable(session, user_input):
    """test if timetable is allowed to be fetched"""
    day = datetime.date.today()
    school_years = session.schoolyears()
    if not get_schoolyear(school_year=school_years):
        day = school_years[-1].start.date()

    try:
        if user_input["timetable_source"] == "personal":
            session.my_timetable(start=day, end=day)
        else:
            timetable_object = get_timetable_object(
                user_input["timetable_source_id"],
                user_input["timetable_source"],
                session,
            )
            session.timetable(
                start=day,
                end=day,
                **timetable_object,
            )

    except Exception as exc:

        if str(exc) == "'Student not found'":
            return {"base": "student_not_found"}
        elif str(exc) == "no right for timetable":
            return {"base": "no_rights_for_timetable"}

        _LOGGER.error("Error testing timetable: %s", exc)
        return {"base": "unknown"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for webuntisnew."""

    VERSION = CONFIG_ENTRY_VERSION

    _session_temp = None
    _user_input_temp = {}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            errors, self._session_temp = await validate_login(self.hass, user_input)

            if not errors:
                self._user_input_temp = user_input
                return await self.async_step_timetable_source()

        user_input = user_input or {}

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
                }
            ),
            errors=errors,
        )

    async def async_step_timetable_source(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._user_input_temp.update(
                {"timetable_source": user_input["timetable_source"]}
            )
            if user_input["timetable_source"] == "personal":
                self._user_input_temp.update(user_input)
                self._user_input_temp.update({"timetable_source_id": "personal"})
                errors = await self.hass.async_add_executor_job(
                    test_timetable, self._session_temp, self._user_input_temp
                )
                if not errors:
                    return await self.create_entry()
            elif user_input["timetable_source"] == "student":
                return await self.async_step_pick_student()

            elif user_input["timetable_source"] == "teacher":
                return await self.async_step_pick_teacher()

            elif user_input["timetable_source"] == "klasse":
                school_years = await self.hass.async_add_executor_job(
                    self._session_temp.schoolyears
                )
                school_year = bool(get_schoolyear(school_years))
                if school_year:
                    return await self.async_step_pick_klasse()
                else:
                    errors = {"base": "no_school_year"}

        return self.async_show_form(
            errors=errors,
            step_id="timetable_source",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "timetable_source",
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "personal",
                                "student",
                                "klasse",
                                "teacher",
                            ],  # "subject", "room"
                            translation_key="timetable_source",
                        )
                    )
                }
            ),
        )

    async def async_step_pick_student(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            self._user_input_temp.update(
                {
                    "timetable_source": "student",
                    "timetable_source_id": [
                        user_input["fore_name"],
                        user_input["surname"],
                    ],
                }
            )

            errors = await self.hass.async_add_executor_job(
                test_timetable, self._session_temp, self._user_input_temp
            )
            if not errors:
                return await self.create_entry()

        return self.async_show_form(
            errors=errors,
            step_id="pick_student",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "fore_name",
                    ): str,
                    vol.Required(
                        "surname",
                    ): str,
                }
            ),
        )

    async def async_step_pick_teacher(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            self._user_input_temp.update(
                {
                    "timetable_source": "teacher",
                    "timetable_source_id": [
                        user_input["fore_name"],
                        user_input["surname"],
                    ],
                }
            )
            errors = await self.hass.async_add_executor_job(
                test_timetable, self._session_temp, self._user_input_temp
            )
            if not errors:
                return await self.create_entry()

        return self.async_show_form(
            errors=errors,
            step_id="pick_teacher",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "fore_name",
                    ): str,
                    vol.Required(
                        "surname",
                    ): str,
                }
            ),
        )

    async def async_step_pick_klasse(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors = {}
        if user_input is not None:

            klassen = await self.hass.async_add_executor_job(self._session_temp.klassen)
            try:
                source = klassen.filter(name=user_input["klasse"])[0]
            except Exception as exc:
                errors = {"base": "klasse_not_found"}

            self._user_input_temp.update(
                {
                    "timetable_source": "klasse",
                    "timetable_source_id": user_input["klasse"],
                }
            )

            errors = await self.hass.async_add_executor_job(
                test_timetable, self._session_temp, self._user_input_temp
            )
            if not errors:
                return await self.create_entry()

        return self.async_show_form(
            errors=errors,
            step_id="pick_klasse",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "klasse",
                    ): str
                }
            ),
        )

    async def create_entry(self):

        user_input = self._user_input_temp
        await self.async_set_unique_id(
            # pylint: disable=consider-using-f-string
            "{username}@{timetable_source_id}@{school}".format(**user_input)
            .lower()
            .replace(" ", "-")
        )
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=user_input["username"],
            data=user_input,
            options=DEFAULT_OPTIONS,
        )

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
                            translation_key="timetable_source",
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


OPTIONS_MENU = [
    "filter",
    "calendar",
    "lesson",
    "notify_menu",
    "backend",
]


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle the option flow for WebUntis."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,  # pylint: disable=unused-argument
    ) -> FlowResult:
        """Manage the options."""
        return self.async_show_menu(step_id="init", menu_options=OPTIONS_MENU)

    async def save(self, user_input):
        """Save the options"""
        _LOGGER.debug("Saving options: %s", user_input)
        options = dict(self.config_entry.options)  # old options
        options.update(user_input)  # update old options with new options
        _LOGGER.debug("New options: %s", options)
        return self.async_create_entry(title="", data=options)

    async def async_step_filter(self, user_input: dict[str, str] = None) -> FlowResult:
        """Manage the filter options."""
        if user_input is not None:
            if not "filter_description" in user_input:
                user_input["filter_description"] = []

            if user_input["filter_mode"] and not user_input["filter_subjects"]:
                user_input["filter_mode"] = "None"

            if user_input["filter_description"]:
                user_input["extended_timetable"] = True
                user_input["filter_description"] = user_input[
                    "filter_description"
                ].split(",")
                user_input["filter_description"] = [
                    s.strip() for s in user_input["filter_description"] if s != ""
                ]

            return await self.save(user_input)

        server = self.hass.data[DOMAIN][self.config_entry.unique_id]

        return self.async_show_form(
            step_id="filter",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "filter_mode",
                        default=str(self.config_entry.options.get("filter_mode")),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "None",
                                "Blacklist",
                                "Whitelist",
                            ],
                            mode="dropdown",
                        )
                    ),
                    vol.Required(
                        "filter_subjects",
                        default=self.config_entry.options.get("filter_subjects"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_create_subject_list(server),
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Optional(
                        "filter_description",
                        description={
                            "suggested_value": ", ".join(
                                self.config_entry.options.get("filter_description")
                            )
                        },
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(multiline=True)
                    ),
                    vol.Required(
                        "invalid_subjects",
                        default=self.config_entry.options.get("invalid_subjects"),
                    ): selector.BooleanSelector(),
                }
            ),
        )

    async def async_step_calendar(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Manage the calendar options."""
        errors = {}
        if user_input is not None:
            if user_input["calendar_description"] == "Lesson Info":
                user_input["extended_timetable"] = True

            if not (
                isinstance(user_input.get("calendar_replace_name"), dict)
                and all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in user_input["calendar_replace_name"].items()
                )
            ):
                errors = {"calendar_replace_name": "not_a_dict"}
            else:
                return await self.save(user_input)

        return self.async_show_form(
            step_id="calendar",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "calendar_show_cancelled_lessons",
                        default=self.config_entry.options.get(
                            "calendar_show_cancelled_lessons"
                        ),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "calendar_show_room_change",
                        default=self.config_entry.options.get(
                            "calendar_show_room_change"
                        ),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "calendar_description",
                        default=str(
                            self.config_entry.options.get("calendar_description")
                        ),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "None",
                                "JSON",
                                "Lesson Info",
                            ],
                            mode="dropdown",
                        )
                    ),
                    vol.Required(
                        "calendar_room",
                        default=str(self.config_entry.options.get("calendar_room")),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "Room long name",
                                "Room short name",
                                "Room short-long name",
                                "None",
                            ],
                            mode="dropdown",
                        )
                    ),
                    vol.Optional(
                        "calendar_replace_name",
                        description={
                            "suggested_value": self.config_entry.options.get(
                                "calendar_replace_name"
                            )
                        },
                    ): selector.ObjectSelector(),
                }
            ),
        )

    async def async_step_lesson(self, user_input: dict[str, str] = None) -> FlowResult:
        """Manage the lesson options."""
        errors = {}
        if user_input is not None:

            if not (
                isinstance(user_input.get("lesson_replace_name"), dict)
                and all(
                    isinstance(k, str) and isinstance(v, str)
                    for k, v in user_input["lesson_replace_name"].items()
                )
            ):
                errors = {"lesson_replace_name": "not_a_dict"}
            else:
                return await self.save(user_input)

        server = self.hass.data[DOMAIN][self.config_entry.unique_id]

        return self.async_show_form(
            step_id="lesson",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "lesson_long_name",
                        default=self.config_entry.options.get("lesson_long_name"),
                    ): selector.BooleanSelector(),
                    vol.Optional(
                        "lesson_replace_name",
                        description={
                            "suggested_value": self.config_entry.options.get(
                                "lesson_replace_name"
                            )
                        },
                    ): selector.ObjectSelector(),
                    vol.Optional(
                        "lesson_add_teacher",
                        default=self.config_entry.options.get("lesson_add_teacher"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_create_subject_list(server),
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                }
            ),
        )

    async def async_step_backend(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the backend options."""
        if user_input is not None:
            if (
                not user_input["extended_timetable"]
                and self.config_entry.options["filter_description"]
            ):
                errors = {"extended_timetable": "extended_timetable"}
            elif (
                user_input["extended_timetable"] is False
                and self.config_entry.options["calendar_description"] == "Lesson Info"
            ):
                errors = {"extended_timetable": "extended_timetable"}
            else:
                return await self.save(user_input)
        return self.async_show_form(
            step_id="backend",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "keep_loged_in",
                        default=self.config_entry.options.get("keep_loged_in"),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "generate_json",
                        default=self.config_entry.options.get("generate_json"),
                    ): selector.BooleanSelector(),
                    vol.Required(
                        "exclude_data",
                        default=self.config_entry.options.get("exclude_data"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["teachers"],
                            multiple=True,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        ),
                    ),
                    vol.Required(
                        "extended_timetable",
                        default=self.config_entry.options.get("extended_timetable"),
                    ): selector.BooleanSelector(),
                }
            ),
            errors=errors,
        )

    async def list_notify_services(
        self, step_id, multible=False, required=True, errors={}
    ):
        services = {
            id: service["name"]
            for id, service in self.config_entry.options["notify_config"].items()
        }

        select = cv.multi_select if multible else vol.In
        required = vol.Required if required else vol.Optional

        return self.async_show_form(
            step_id=step_id,
            errors=errors,
            data_schema=vol.Schema(
                {
                    required("services"): select(services),
                }
            ),
        )

    async def async_step_notify_menu(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the notify_menu options."""

        if not self.config_entry.options["notify_config"]:
            options = [
                "edit_notify_service",
            ]
        else:
            options = [
                "edit_notify_service",
                "edit_notify_service_select",
                "remove_notify_service",
                "test_notify_service",
            ]
        return self.async_show_menu(step_id="notify_menu", menu_options=options)

    async def async_step_edit_notify_service_select(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the test options."""
        if user_input is None:
            return await self.list_notify_services("edit_notify_service_select")
        else:
            return await self.async_step_edit_notify_service(
                edit=user_input["services"]
            )

    async def async_step_remove_notify_service(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the test options."""
        if user_input is None:
            return await self.list_notify_services(
                "remove_notify_service", multible=True
            )
        else:
            notify_config = self.config_entry.options["notify_config"]
            for key in user_input["services"]:
                notify_config.pop(key, None)
            return await self.save(
                {
                    "notify_config": notify_config,
                    "toggle": not self.config_entry.options.get("toggle"),
                }
            )

    async def async_step_test_notify_service(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Manage the test options."""
        if user_input is None:
            return await self.list_notify_services(
                "test_notify_service", multible=True, required=False, errors=errors
            )
        else:
            for service in user_input.get("services", {}):

                config = self.config_entry.options["notify_config"][service]

                data = {
                    "data": config.get("data", {}),
                    "target": config.get("target", {}),
                }

                changes = {
                    "change": "test",
                    "title": "Test Notification",
                    "subject": "Math",
                    "date": datetime.datetime.now().strftime("%d.%m.%Y"),
                    "time_start": datetime.datetime.now().strftime("%H:%M:%S"),
                    "time_end": datetime.datetime.now().strftime("%H:%M:%S"),
                }

                data.update(
                    get_notification_data(changes, config, self.config_entry.title)
                )

                success = await async_notify(
                    self.hass,
                    service_id=config["entity_id"],
                    data=data,
                )
                if not success:
                    return await self.async_step_test_notify_service(
                        None, errors={"base": "notification_invalid"}
                    )

            return await self.save({})

    async def async_step_edit_notify_service(
        self,
        user_input: dict[str, str] = None,
        errors: dict[str, Any] | None = None,
        edit=None,
    ) -> FlowResult:

        options = {}
        if edit:
            options = self.config_entry.options["notify_config"].get(edit)

        if user_input is not None:
            errors = {}

            if "entity_id" in user_input and not is_service(
                self.hass, user_input["entity_id"]
            ):
                errors["entity_id"] = "unknown_service"

            if "notify_target" in user_input and not isinstance(
                user_input["target"], dict
            ):
                errors["notify_target"] = "not_a_dict"

            if "notify_data" in user_input and not isinstance(user_input["data"], dict):
                errors["notify_data"] = "not_a_dict"

            if "name" not in user_input:
                user_input["name"] = user_input["entity_id"]

            if not errors:
                notify_config = self.config_entry.options["notify_config"]
                notify_config[user_input["entity_id"]] = user_input

                return await self.save(
                    {
                        "notify_config": notify_config,
                        "toggle": not self.config_entry.options.get("toggle"),
                    }
                )

            options = self.config_entry.options["notify_config"].get(
                user_input["entity_id"], {}
            )

        schema_options = {
            vol.Optional(
                "name",
                description={"suggested_value": options.get("name")},
            ): selector.TextSelector(),
            vol.Required(
                "entity_id",
                description={"suggested_value": options.get("entity_id")},
            ): selector.TextSelector(),
            vol.Optional(
                "target",
                description={"suggested_value": options.get("target")},
            ): selector.ObjectSelector(selector.ObjectSelectorConfig()),
            vol.Optional(
                "data",
                description={"suggested_value": options.get("data")},
            ): selector.ObjectSelector(),
            vol.Optional(
                "template",
                description={
                    "suggested_value": options.get("template", TEMPLATE_OPTIONS[0])
                },
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=TEMPLATE_OPTIONS,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="notify_template",
                )
            ),
            vol.Optional(
                "options",
                description={"suggested_value": options.get("options")},
            ): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=NOTIFY_OPTIONS,
                    multiple=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                    translation_key="notify_options",
                )
            ),
        }

        return self.async_show_form(
            step_id="edit_notify_service",
            data_schema=vol.Schema(schema_options),
            errors=errors,
        )


def _create_subject_list(server):
    """Create a list of subjects."""

    subjects = server.subjects

    return [subject.name for subject in subjects]
