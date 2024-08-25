"""Config flow for webuntisnew integration."""

from __future__ import annotations

import datetime
import logging
import socket
from typing import Any
from urllib.parse import urlparse

import requests
import voluptuous as vol

# import webuntis.session

# pylint: disable=maybe-no-member
import webuntis
from .utils.login_qr import login_qr


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
from .utils.utils import async_notify, get_schoolyear, is_service

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

    if credentials["login_method"] == "qr-code":
        try:
            session = await hass.async_add_executor_job(
                login_qr,
                credentials["server"],
                credentials["school"],
                credentials["user"],
                credentials["key"],
            )
        except BadCredentials:
            errors["base"] = "invalid_auth"

    elif credentials["login_method"] == "password":

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


async def validate_input(
    hass: HomeAssistant, user_input: dict[str, Any]
) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    if user_input["timetable_source"] in ["student", "teacher"] and isinstance(
        user_input["timetable_source_id"], str
    ):
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
        _LOGGER.error("Cannot resolve hostname: %s", exc)
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
        _LOGGER.error("webuntis.Session connection error: %s", exc)
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


def test_timetable(session, timetable_source, source=None):
    """test if timetable is allowed to be fetched"""
    day = datetime.date.today()
    school_years = session.schoolyears()
    if not get_schoolyear(school_year=school_years):
        day = school_years[-1].start.date()

    try:
        if timetable_source == "own":
            session.my_timetable(start=day, end=day)
        else:
            session.timetable(start=day, end=day, **{timetable_source: source})
    except Exception as exc:
        _LOGGER.error("Error testing timetable: %s", exc)
        return {"base", "error"}


CONFIG_MENU = ["login_password", "qr_code"]


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
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return self.async_show_menu(step_id="user", menu_options=CONFIG_MENU)

    async def async_step_qr_code(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:

        if user_input is not None:
            errors, self._session_temp = await validate_login(
                self.hass, {**user_input, "login_method": "qr-code"}
            )
            if not errors:
                self._user_input_temp = user_input
                return await self.async_step_timetable_source()

        return self.async_show_form(
            step_id="qr_code",
            errors=errors,
            data_schema=vol.Schema(
                {
                    vol.Required("server"): str,
                    vol.Required("school"): str,
                    vol.Required("user"): str,
                    vol.Required("key"): str,
                }
            ),
        )

    async def async_step_login_password(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, Any] | None = None,
    ) -> FlowResult:
        if user_input is not None:
            errors, self._session_temp = await validate_login(
                self.hass, {**user_input, "login_method": "password"}
            )

            if not errors:
                self._user_input_temp = user_input
                return await self.async_step_timetable_source()

        user_input = user_input or {}

        return self.async_show_form(
            step_id="login_password",
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
        if user_input is not None:
            if user_input["timetable_source"] == "own":
                errors = await self.hass.async_add_executor_job(
                    test_timetable, self._session_temp, "own"
                )
                if not errors:
                    self._user_input_temp.update(user_input)
                    self._user_input_temp.update({"timetable_source_id": "personal"})
                    return await self.create_entry()

        return self.async_show_form(
            step_id="timetable_source",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "timetable_source",
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                "own",
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

    async def async_step_login_password_(
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
            errors["server"] = "cannot_connect"
        except InvalidAuth:
            errors["name"] = "invalid_auth"
        except BadCredentials:
            errors["name"] = "bad_credentials"
        except SchoolNotFound:
            errors["school"] = "school_not_found"
        except NameSplitError:
            errors["timetable_source_id"] = "name_split_error"
        except StudentNotFound:
            errors["timetable_source_id"] = "student_not_found"
        except TeacherNotFound:
            errors["timetable_source_id"] = "teacher_not_found"
        except ClassNotFound:
            errors["timetable_source_id"] = "class_not_found"
        except NoRightsForTimetable:
            errors["timetable_source_id"] = "no_rights_for_timetable"

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
                }
            ),
        )

    async def async_step_calendar(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Manage the calendar options."""
        if user_input is not None:
            if user_input["calendar_description"] == "Lesson Info":
                user_input["extended_timetable"] = True

            return await self.save(user_input)

        return self.async_show_form(
            step_id="calendar",
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
