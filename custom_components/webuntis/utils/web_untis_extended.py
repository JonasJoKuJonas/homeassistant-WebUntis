import json
import logging
from collections.abc import Iterable
from datetime import date, datetime, timedelta, timezone
from typing import ClassVar

import aiohttp
import requests
from webuntis import errors, objects
from webuntis.session import Session as WebUntisSession
from webuntis.utils.logger import log

from .qrLogin import QrData, async_qr_login, extract_login_result
from .rest_timetable import RestTimetableError, get_rest_lessons
from .schoolyears import resolve_schoolyear

QR_USER_AGENT = "UntisMobileAndroid"
QR_API_VERSION = "i3.2"


class _GetTeachersPermissionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "no right for getTeachers()" not in record.getMessage()


class ExtendedSession(WebUntisSession):
    """
    This class extends the original Session to include new functionality for
    fetching homeworks from the WebUntis API using a different endpoint.
    It also includes a fallback mechanism for fetching teacher information in
    case the server forbids fetching teachers directly.
    """

    _ELEMENT_TYPE_TABLE: ClassVar[dict[str, int]] = {
        "klasse": 1,
        "teacher": 2,
        "subject": 3,
        "room": 4,
        "student": 5,
    }

    _REST_MASTER_DATA_KEYS: ClassVar[dict[str, str]] = {
        "su": "subjects",
        "te": "teachers",
        "ro": "rooms",
        "kl": "klassen",
    }

    @classmethod
    async def async_create_from_qr(
        cls,
        credentials: QrData,
        client_session: aiohttp.ClientSession,
    ) -> tuple["ExtendedSession", str]:
        """Create an authenticated ExtendedSession from QR credentials."""
        user_data, jsessionid = await async_qr_login(credentials, client_session)

        session = cls(
            server=f"https://{credentials.server}",
            school=credentials.school,
            username=credentials.user,
            password="",
            jsessionid=jsessionid,
            useragent="home-assistant",
        )

        session.login_result = extract_login_result(user_data)
        return session, jsessionid

    async def async_refresh_qr(
        self,
        credentials: QrData,
        client_session: aiohttp.ClientSession,
    ) -> None:
        """Refresh JSESSIONID using QR credentials."""
        user_data, jsessionid = await async_qr_login(credentials, client_session)

        self.config["jsessionid"] = jsessionid
        self.login_result = extract_login_result(user_data)

        session = getattr(self, "_session", None)
        if session is not None:
            session.cookies.set("JSESSIONID", jsessionid)

    def _request(self, method, params=None, use_login_repeat=None):
        if use_login_repeat is None and (
            "password" not in self.config or not self.config["password"]
        ):
            use_login_repeat = False

        try:
            return super()._request(  # type: ignore[attr-defined]
                method,
                params=params,
                use_login_repeat=use_login_repeat,
            )
        except errors.RemoteError as err:
            # Catch the schoolyear not found error from Untis.
            if err.code == -8998 or ("schoolyear" in str(err) and "null" in str(err)):
                return []
            raise

    def _send_custom_request(self, endpoint, params):
        """
        Send a request to a custom WebUntis REST endpoint.

        :param endpoint: API endpoint.
        :param params: Query parameters.
        :return: JSON response.
        """
        base_url = self.config["server"].replace("/WebUntis/jsonrpc.do", "")
        url = f"{base_url}{endpoint}"

        headers = {
            "User-Agent": self.config["useragent"],
            "Content-Type": "application/json",
        }

        if "jsessionid" in self.config:
            headers["Cookie"] = f"JSESSIONID={self.config['jsessionid']}"
        else:
            raise errors.NotLoggedInError("No JSESSIONID found. Please log in first.")

        log("debug", f"Making custom request to {url} with params: {params}")

        response = requests.get(url, params=params, headers=headers)

        try:
            response_data = response.json()
            log(
                "debug",
                f"Received valid JSON response: {str(response_data)[:100]}",
            )
        except json.JSONDecodeError:
            raise errors.RemoteError(
                "Invalid JSON response",
                response.text,
            )

        return response_data

    def get_homeworks(self, start, end):
        """
        Fetch homeworks for lessons within a specific date range.

        :param start: Start date.
        :param end: End date.
        :return: JSON response containing homework data.
        """
        endpoint = "/WebUntis/api/homeworks/lessons"

        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        return self._send_custom_request(endpoint, params)

    def get_exams(self, start, end):
        """
        Fetch exams within a specific date range.

        :param start: Start date.
        :param end: End date.
        :return: JSON response containing exam data.
        """
        endpoint = "/WebUntis/api/exams"

        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        return self._send_custom_request(endpoint, params)

    def _update_teacher_mapping(
        self,
        start: date | datetime | int,
        end: date | datetime | int,
        element_type_num: int,
        element_id: int,
    ):
        """
        Fetch all teachers from timetable data and build a teacher mapping.

        This mapping is used when direct access to getTeachers() is forbidden.
        """
        params = {
            "options": {
                "element": {
                    "id": str(element_id),
                    "type": str(element_type_num),
                },
                "startDate": (
                    int(start.strftime("%Y%m%d"))
                    if isinstance(start, (date, datetime))
                    else start
                ),
                "endDate": (
                    int(end.strftime("%Y%m%d"))
                    if isinstance(end, (date, datetime))
                    else end
                ),
                "teacherFields": ["id", "name"],
            }
        }

        teacher_map = {}

        try:
            result = self._request(method="getTimetable", params=params)

            if result:
                for period in result:
                    for teacher in period.get("te", []):
                        if "id" in teacher:
                            teacher_map[teacher["id"]] = teacher.get(
                                "name",
                                str(teacher["id"]),
                            )

                        if "orgid" in teacher:
                            teacher_map[teacher["orgid"]] = teacher.get(
                                "orgname",
                                str(teacher["orgid"]),
                            )

        except (
            requests.RequestException,
            errors.RemoteError,
            errors.NotLoggedInError,
        ) as err:
            log(
                "warning",
                f"Teacher mapping update failed: {err}. "
                "This may lead to missing teacher names in the timetable.",
            )
        except Exception as err:
            log(
                "error",
                f"Unexpected error while updating teacher mapping: {err}",
            )
            raise

        if not hasattr(self, "teacher_map"):
            self.teacher_map = teacher_map
        else:
            self.teacher_map.update(teacher_map)

    def _register_rest_master_data(
        self,
        jsonrpc_key: str,
        elements: Iterable[dict],
    ) -> None:
        """
        Store master data discovered through the REST timetable.

        REST timetable data can contain IDs which are missing from the
        corresponding JSON-RPC master-data response. Keeping these entries
        separately allows the regular python-webuntis object resolution to
        use them later.
        """
        if not hasattr(self, "_rest_master_data"):
            self._rest_master_data = {}

        master_data = self._rest_master_data.setdefault(jsonrpc_key, {})

        for element in elements:
            element_id = element.get("id")
            if element_id is None:
                continue

            normalized = {
                "id": element_id,
                "name": element.get("name") or "",
                "longName": element.get("long_name") or "",
            }

            existing = master_data.get(element_id)

            if existing is None:
                master_data[element_id] = normalized
                continue

            if not existing["name"] and normalized["name"]:
                existing["name"] = normalized["name"]

            if not existing["longName"] and normalized["longName"]:
                existing["longName"] = normalized["longName"]

    def _merge_rest_master_data(
        self,
        collection,
        jsonrpc_key: str,
    ):
        """
        Merge REST-discovered master data into a python-webuntis collection.
        """
        rest_master_data = getattr(self, "_rest_master_data", {}).get(
            jsonrpc_key,
            {},
        )

        if not rest_master_data:
            return collection

        existing_ids = {getattr(item, "id", None) for item in collection}

        for element in rest_master_data.values():
            element_id = element["id"]

            if element_id in existing_ids:
                continue

            collection._data.append(dict(element))
            existing_ids.add(element_id)

        return collection

    def rooms(self, **kw_args):
        """Return rooms including rooms discovered through the REST timetable."""
        result = super().rooms(**kw_args)
        return self._merge_rest_master_data(result, "ro")

    def subjects(self, **kw_args):
        """Return subjects including subjects discovered through the REST timetable."""
        result = super().subjects(**kw_args)
        return self._merge_rest_master_data(result, "su")

    def klassen(self, **kw_args):
        """Return classes including classes discovered through the REST timetable."""
        result = super().klassen(**kw_args)
        return self._merge_rest_master_data(result, "kl")

    def teachers(self, **kw_args):
        """
        Get teachers with a fallback when getTeachers() is forbidden.

        REST-discovered teachers are also merged into the returned collection.
        """
        result = None

        if not getattr(self, "teachers_forbidden", False):
            upstream_logger = logging.getLogger("webuntis")
            log_filter = _GetTeachersPermissionFilter()
            upstream_logger.addFilter(log_filter)

            try:
                result = super().teachers(**kw_args)

                if not result:
                    log(
                        "debug",
                        "Fetching teachers returned an empty result. "
                        "Assuming fetching teachers is forbidden and using "
                        "fallback mechanism.",
                    )
                    self.teachers_forbidden = True
                    result = None
                else:
                    self.teachers_forbidden = False

            except Exception as err:
                if getattr(err, "code", None) == -8509 or (
                    "no right for getTeachers()" in str(err)
                ):
                    log(
                        "debug",
                        f"Fetching teachers failed with error: {err}. "
                        "Assuming fetching teachers is forbidden and using "
                        "fallback mechanism.",
                    )
                    self.teachers_forbidden = True
                else:
                    raise

            finally:
                upstream_logger.removeFilter(log_filter)

        if getattr(self, "teachers_forbidden", False):
            if not hasattr(self, "teacher_map"):
                if not hasattr(self, "_last_used_timetable_source"):
                    self._last_used_timetable_source = (
                        self.login_result["personType"],
                        self.login_result["personId"],
                    )

                log(
                    "debug",
                    "Teacher map not found. Fetching teacher mapping using "
                    f"fallback mechanism for element type "
                    f"{self._last_used_timetable_source[0]} and element id "
                    f"{self._last_used_timetable_source[1]}.",
                )

                starttime = datetime.now(timezone.utc)
                schoolyears = self.schoolyears()

                if schoolyears:
                    currentschoolyear = resolve_schoolyear(schoolyears)

                    if currentschoolyear:
                        starttime = max(
                            starttime,
                            currentschoolyear.start.replace(tzinfo=timezone.utc),
                        )
                        endtime = min(
                            starttime + timedelta(days=7),
                            currentschoolyear.end.replace(tzinfo=timezone.utc),
                        )

                        self._update_teacher_mapping(
                            start=starttime,
                            end=endtime,
                            element_type_num=self._last_used_timetable_source[0],
                            element_id=self._last_used_timetable_source[1],
                        )

            data = [
                {
                    "id": teacher_id,
                    "name": name,
                    "longName": name,
                    "foreName": name,
                    "title": "",
                }
                for teacher_id, name in self.teacher_map.items()
            ]

            result = objects.TeacherList(
                session=self,
                data=data,
            )

        return self._merge_rest_master_data(result, "te")

    def _collect_teacher_ids(self, result):
        """Collect all teacher IDs and original teacher IDs from timetable results."""
        teacher_ids = []

        for lesson in result:
            for entry in getattr(lesson, "_data", {}).get("te", []):
                if entry.get("id") is not None:
                    teacher_ids.append(entry["id"])

                if entry.get("orgid") is not None:
                    teacher_ids.append(entry["orgid"])

        return teacher_ids

    def _ensure_teacher_mapping(
        self,
        result,
        start,
        end,
        element_type_num,
        element_id,
    ):
        """Ensure teacher mapping is up-to-date if teachers are forbidden."""
        self._last_used_timetable_source = (
            element_type_num,
            int(element_id),
        )

        if not hasattr(self, "teachers_forbidden"):
            self.teachers()

        if getattr(self, "teachers_forbidden", False):
            teacher_ids = self._collect_teacher_ids(result)

            if not set(teacher_ids).issubset(
                set(getattr(self, "teacher_map", {}).keys())
            ):
                try:
                    self._update_teacher_mapping(
                        start=start,
                        end=end,
                        element_type_num=element_type_num,
                        element_id=int(element_id),
                    )
                except (OSError, errors.RemoteError) as err:
                    log(
                        "warning",
                        f"Teacher mapping update failed: {err}. "
                        "Timetable retrieval will continue.",
                    )
                except Exception as err:
                    log(
                        "error",
                        f"Unexpected error during teacher mapping update: "
                        f"{err}. Timetable retrieval will continue.",
                    )

    def my_timetable(self, end, start):
        result = super().my_timetable(end=end, start=start)

        self._add_rest_fallbacks(result, start, end)

        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self.login_result["personType"],
            element_id=self.login_result["personId"],
        )

        return result

    def timetable_extended(self, start, end, **type_and_id):
        """Get an extended timetable for a specific element."""
        if len(type_and_id) != 1:
            raise TypeError(
                "You have to specify exactly one of the following parameters "
                "by keyword: " + ", ".join(self._ELEMENT_TYPE_TABLE.keys())
            )

        element_type, element_id = next(iter(type_and_id.items()))

        result = super().timetable_extended(
            start=start,
            end=end,
            **type_and_id,
        )

        self._add_rest_fallbacks(result, start, end)

        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self._ELEMENT_TYPE_TABLE.get(element_type),
            element_id=element_id,
        )

        return result

    def timetable(self, start, end, **type_and_id):
        """Get the timetable for a specific element and time period."""
        if len(type_and_id) != 1:
            raise TypeError(
                "You have to specify exactly one of the following parameters "
                "by keyword: " + ", ".join(self._ELEMENT_TYPE_TABLE.keys())
            )

        element_type, element_id = next(iter(type_and_id.items()))

        result = super().timetable(
            start=start,
            end=end,
            **type_and_id,
        )

        self._add_rest_fallbacks(result, start, end)

        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self._ELEMENT_TYPE_TABLE.get(element_type),
            element_id=element_id,
        )

        return result

    def _add_rest_fallbacks(self, result, start, end):
        """Fill empty JSON-RPC lesson fields from the REST timetable."""
        try:
            rest_lessons = get_rest_lessons(self, start, end)
        except (RestTimetableError, requests.RequestException) as err:
            log(
                "debug",
                f"REST timetable fallbacks unavailable: {err}",
            )
            return

        rest_by_time = {
            self._time_key(lesson["start"], lesson["end"]): lesson
            for lesson in rest_lessons
        }

        for lesson in result:
            data = getattr(lesson, "_data", None)

            if not data:
                continue

            fallback = rest_by_time.get(
                self._time_key(
                    lesson.start.isoformat(),
                    lesson.end.isoformat(),
                )
            )

            if not fallback:
                continue

            if not data.get("lstext"):
                data["lstext"] = fallback["lesson_text"] or fallback["lesson_info"]

            if not data.get("substText"):
                data["substText"] = fallback["substitution_text"]

            for jsonrpc_key, rest_key in self._REST_MASTER_DATA_KEYS.items():
                rest_elements = [
                    element
                    for element in fallback[rest_key]
                    if element.get("id") is not None
                ]

                if not rest_elements:
                    continue

                # Register the REST elements globally for this session.
                # This is important because lesson.rooms/subjects/teachers/ klassen resolve their IDs through the session master data.
                self._register_rest_master_data(
                    jsonrpc_key,
                    rest_elements,
                )

                existing_elements = data.setdefault(
                    jsonrpc_key,
                    [],
                )

                existing_by_id = {
                    element.get("id"): element
                    for element in existing_elements
                    if element.get("id") is not None
                }

                for element in rest_elements:
                    existing = existing_by_id.get(element["id"])

                    if existing is None:
                        existing = {
                            "id": element["id"],
                            "name": element.get("name") or "",
                            "longName": element.get("long_name") or "",
                        }
                        existing_elements.append(existing)
                        existing_by_id[element["id"]] = existing
                        continue

                    if not existing.get("name") and element.get("name"):
                        existing["name"] = element["name"]

                    if not existing.get("longName") and element.get("long_name"):
                        existing["longName"] = element["long_name"]

    @staticmethod
    def _time_key(start, end):
        return tuple(value[:19] for value in (start, end))
