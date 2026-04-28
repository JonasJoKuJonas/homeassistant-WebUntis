import requests
import json
from webuntis import errors, objects
from datetime import datetime, timedelta, date
from webuntis.utils import log  # pylint: disable=no-name-in-module
from webuntis.session import Session as WebUntisSession

import logging

# logging.basicConfig(level=logging.DEBUG)


class ExtendedSession(WebUntisSession):
    """
    This class extends the original Session to include new functionality for
    fetching homeworks from the WebUntis API using a different endpoint.
    It also includes a fallback mechanism for fetching teacher information in case the server forbids fetching teachers directly.
    """

    def _send_custom_request(self, endpoint, params):
        """
        A custom method for sending a request to a specific endpoint, different from the JSON-RPC method.

        :param endpoint: The API endpoint for the custom request (e.g., '/api/homeworks/lessons')
        :param params: The query parameters for the request
        :return: JSON response from the API
        """

        base_url = self.config["server"].replace("/WebUntis/jsonrpc.do", "")

        # Construct the URL
        url = f"{base_url}{endpoint}"

        # Prepare headers
        headers = {
            "User-Agent": self.config["useragent"],
            "Content-Type": "application/json",
        }

        # Ensure session is logged in
        if "jsessionid" in self.config:
            headers["Cookie"] = f"JSESSIONID={self.config['jsessionid']}"
        else:
            raise errors.NotLoggedInError("No JSESSIONID found. Please log in first.")

        # Log the request details
        log("debug", f"Making custom request to {url} with params: {params}")

        # Send the request using requests library
        response = requests.get(url, params=params, headers=headers)

        # Check if the response is valid JSON
        try:
            response_data = response.json()
            log("debug", f"Received valid JSON response: {str(response_data)[:100]}")
        except json.JSONDecodeError:
            raise errors.RemoteError("Invalid JSON response", response.text)

        return response_data

    def get_homeworks(self, start, end):
        """
        Fetch homeworks for lessons within a specific date range using the
        '/api/homeworks/lessons' endpoint.

        :param start_date: Start date in the format YYYYMMDD (e.g., 20240901)
        :param end_date: End date in the format YYYYMMDD (e.g., 20240930)
        :return: JSON response containing homework data
        """
        # Define the custom endpoint
        endpoint = "/WebUntis/api/homeworks/lessons"

        # Set query parameters
        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        # Send the request and return the response
        return self._send_custom_request(endpoint, params)

    def get_exams(self, start, end):
        """
        Fetch exams within a specific date range using the
        '/api/homeworks/exams' endpoint.

        :param start_date: Start date in the format YYYYMMDD (e.g., 20240901)
        :param end_date: End date in the format YYYYMMDD (e.g., 20240930)
        :return: JSON response containing exams data
        """
        # Define the custom endpoint
        endpoint = "/WebUntis/api/exams"

        # Set query parameters
        params = {
            "startDate": start.strftime("%Y%m%d"),
            "endDate": end.strftime("%Y%m%d"),
        }

        # Send the request and return the response
        return self._send_custom_request(endpoint, params)

    def _update_teacher_mapping(
        self,
        start: date | datetime | int,
        end: date | datetime | int,
        element_type_num: int,
        element_id: int,
    ):
        """
        Fetches all teachers and builds a mapping of teacher ID to teacher name.
        This mapping is used as fallback to get the short name of the teachers in case fetching teachers directly is forbidden by the server.
        This way the functionality the Webuntis APP provides is recreated.

        :param start: Start date for fetching the timetable (used to get the relevant teachers)
        :param end: End date for fetching the timetable (used to get the relevant teachers)
        :param element_type_num: numerical type of the element for which the timetable is fetched (e.g., teacher, class, etc.)
        :param element_id: The ID of the element for which the timetable is fetched
        """

        params = {
            "options": {
                "element": {"id": str(element_id), "type": str(element_type_num)},
                "startDate": int(start.strftime("%Y%m%d"))
                if isinstance(start, (date, datetime))
                else start,
                "endDate": int(end.strftime("%Y%m%d"))
                if isinstance(end, (date, datetime))
                else end,
                "teacherFields": ["id", "name"],
            }
        }

        result = self._request(method="getTimetable", params=params)

        # Build teacher ID -> name mapping
        teacher_map = {}
        for period in result:
            for t in period.get("te", []):
                if "id" in t:
                    if "name" in t:
                        teacher_map[t["id"]] = t["name"]
                    else:
                        teacher_map[t["id"]] = (
                            f"{t['id']}"  # no name given, use id as name to prevent errors
                        )
                if "orgid" in t:
                    if "orgname" in t:
                        teacher_map[t["orgid"]] = t["orgname"]
                    else:
                        teacher_map[t["orgid"]] = (
                            f"{t['orgid']}"  # no orgname given, use orgid as name to prevent errors
                        )

        if not hasattr(self, "teacher_map"):
            self.teacher_map = teacher_map
        else:
            self.teacher_map.update(teacher_map)

    def teachers(self, **kw_args):
        """
        Public method to get teacher mapping with optional caching.

        :param use_cache: Whether to use cached data if available.

        """
        # override original function to add fallback mechanism in case fetching teachers is forbidden by the server
        # in this case the teacher name that is given in the timetable is used to build a mapping of teacher id to teacher name. This is not ideal but at least gives some information about the teachers.
        result = None
        if not getattr(
            self, "teachers_forbidden", False
        ):  # only do this when we haven't already determined that fetching teachers is forbidden, otherwise we would do unnecessary requests to the server
            try:
                result = super().teachers(**kw_args)
                self.teachers_forbidden = False
            except Exception as e:
                if getattr(
                    e, "code", None
                ) == -8509 or "no right for getTeachers()" in str(
                    e
                ):  # -8509 is the error code for "fetching teachers is forbidden"
                    log(
                        "debug",
                        f"Fetching teachers failed with error: {e}. Assuming fetching teachers is forbidden and using fallback mechanism.",
                    )
                    self.teachers_forbidden = True
                else:
                    raise  # all other exceptions should be raised as they are not related to fetching teachers being forbidden

        if getattr(self, "teachers_forbidden", False):
            if not hasattr(self, "teacher_map"):
                self._update_teacher_mapping(
                    start=datetime.now(),
                    end=datetime.now() + timedelta(days=1),
                    element_type_num=self.login_result["personType"],
                    element_id=self.login_result["personId"],
                )
            # apply the mapping to build a list of teachers in the same format as the original function would return it, so that the rest of the code can work with it without needing to know about the fallback mechanism
            data = [
                {
                    "id": id,
                    "name": name,
                    "longName": name,
                    "foreName": name,
                    "title": "",
                }
                for id, name in self.teacher_map.items()
            ]
            result = objects.TeacherList(session=self, data=data)
        return result

    _ELEMENT_TYPE_TABLE = {
        "klasse": 1,
        "teacher": 2,
        "subject": 3,
        "room": 4,
        "student": 5,
    }

    def _collect_teacher_ids(self, result):
        """Collect all teacher IDs and original teacher IDs from timetable results."""
        teidlist = []
        for lesson in result:
            for entry in getattr(lesson, "_data", {}).get("te", []):
                if entry.get("id") is not None:
                    teidlist.append(entry["id"])
                if entry.get("orgid") is not None:
                    teidlist.append(entry["orgid"])
        return teidlist

    def _ensure_teacher_mapping(self, result, start, end, element_type_num, element_id):
        """Ensure teacher mapping is up-to-date if teachers are forbidden."""
        if not hasattr(self, "teachers_forbidden"):
            self.teachers()  # call teachers to set teachers_forbidden attribute
        if getattr(self, "teachers_forbidden", False):
            teidlist = self._collect_teacher_ids(result)
            if not set(teidlist).issubset(set(getattr(self, "teacher_map", {}).keys())):
                try:
                    self._update_teacher_mapping(
                        start=start,
                        end=end,
                        element_type_num=element_type_num,
                        element_id=int(
                            element_id
                        ),  # int() is needed, as sometimes not the id but the object is given, int() extracts the id from the object
                    )
                except (OSError, errors.RemoteError) as e:
                    log(
                        "warning",
                        f"Teacher mapping update failed: {e}. Timetable retrieval will continue.",
                    )
                except Exception as e:
                    log(
                        "error",
                        f"Unexpected error during teacher mapping update: {e}. Timetable retrieval will continue.",
                    )

    # def _timetable_extended_raw(self, end, start, element_id, element_type_num):
    def my_timetable(self, end, start):
        result = super().my_timetable(end=end, start=start)
        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self.login_result["personType"],
            element_id=self.login_result["personId"],
        )
        return result

    def timetable_extended(self, start, end, **type_and_id):
        """Get the timetable for a specific school class and time period.

        Like timetable, but includes more info.
        """
        if len(type_and_id) != 1:
            raise TypeError(
                "You have to specify exactly one of the following parameters by "
                "keyword: " + (", ".join(self._ELEMENT_TYPE_TABLE.keys()))
            )

        element_type, element_id = list(type_and_id.items())[0]
        result = super().timetable_extended(start=start, end=end, **type_and_id)
        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self._ELEMENT_TYPE_TABLE.get(element_type),
            element_id=element_id,
        )
        return result

    def timetable(self, start, end, **type_and_id):
        """Get the timetable for a specific school class and time period.

        :type start: :py:class:`datetime.datetime` or  :py:class:`datetime.date` or int
        :param start: The beginning of the time period.

        :type end: :py:class:`datetime.datetime` or  :py:class:`datetime.date` or int
        :param end: The end of the time period.

        :rtype: :py:class:`webuntis.objects.PeriodList`

        Furthermore you have to explicitly define a klasse, teacher, subject,
        room or student parameter containing the id or the object of the thing
        you want to get a timetable about::

            import datetime
            today = datetime.date.today()
            monday = today - datetime.timedelta(days=today.weekday())
            friday = monday + datetime.timedelta(days=4)

            klasse = s.klassen().filter(id=1)[0]  # schoolclass #1
            tt = s.timetable(klasse=klasse, start=monday, end=friday)

        :raises: :exc:`ValueError`, :exc:`TypeError`
        """
        if len(type_and_id) != 1:
            raise TypeError(
                "You have to specify exactly one of the following parameters by "
                "keyword: " + (", ".join(self._ELEMENT_TYPE_TABLE.keys()))
            )

        element_type, element_id = list(type_and_id.items())[0]
        result = super().timetable(start=start, end=end, **type_and_id)
        self._ensure_teacher_mapping(
            result,
            start=start,
            end=end,
            element_type_num=self._ELEMENT_TYPE_TABLE.get(element_type),
            element_id=element_id,
        )
        return result
