import logging
import uuid
from datetime import date, datetime, timedelta

import requests
from homeassistant.components.calendar import CalendarEvent
from webuntis import errors
from webuntis.utils.datetime_utils import parse_datetime

from ..utils.rest_timetable import RestTimetableError, get_rest_lessons
from ..utils.schoolyears import resolve_schoolyear

_LOGGER = logging.getLogger(__name__)

# Window of the REST timetable scanned for exams marked on lessons
REST_EXAM_DAYS_BACK = 7
REST_EXAM_DAYS_AHEAD = 84
REST_CHUNK_DAYS = 28

# pylint: disable=relative-beyond-top-level
from ..utils.web_untis import get_lesson_name_str


class ExamAuthenticationError(Exception):
    """Raised when exam data is requested without an authenticated session."""


class ExamDataError(Exception):
    """Raised when exam data cannot be fetched from WebUntis."""


class ExamEventsFetcher:
    def __init__(self, server, timezone_str="UTC"):
        self.server = server
        self.session = server.session
        self.event_list = []
        self.current_schoolyear = server.current_schoolyear

    def _get_exam_events(self):
        """
        Fetch exam events from the WebUntis API using the session object and return them as a list of event dictionaries.
        """

        schoolyear = resolve_schoolyear(getattr(self.server, "schoolyears", None))
        if not schoolyear:
            return []

        # Fetch exam data using the session object
        schoolyear_start = schoolyear.start.date()
        schoolyear_end = schoolyear.end.date()
        if schoolyear_start > schoolyear_end:
            return []

        try:
            exam_data = self.session.get_exams(
                start=schoolyear_start,
                end=schoolyear_end,
            )
        except errors.NotLoggedInError:
            raise ExamAuthenticationError(
                "You are not logged in. Please log in and try again."
            ) from None
        except errors.RemoteError as e:
            raise ExamDataError(f"Error fetching exam data: {e}") from e

        # Process the exam data and extract exam events
        exam_events = self._process_exam_data(exam_data)

        # Many schools only mark exams on the lesson itself, which the exam
        # endpoint does not return; add those from the REST timetable.
        try:
            rest_events = self._get_rest_exam_events(schoolyear_start, schoolyear_end)
        except Exception:
            # Optional data source: never let it break the integration setup
            _LOGGER.warning("Could not add exams from the REST timetable", exc_info=True)
            rest_events = []
        known = {(event.start, event.summary) for event in exam_events}
        for event in rest_events:
            if (event.start, event.summary) not in known:
                exam_events.append(event)
        return exam_events

    def _get_rest_exam_events(self, schoolyear_start, schoolyear_end):
        """Return exams marked on lessons in the REST timetable."""
        today = date.today()
        start = max(schoolyear_start, today - timedelta(days=REST_EXAM_DAYS_BACK))
        end = min(schoolyear_end, today + timedelta(days=REST_EXAM_DAYS_AHEAD))

        lessons = []
        chunk_start = start
        while chunk_start <= end:
            chunk_end = min(end, chunk_start + timedelta(days=REST_CHUNK_DAYS - 1))
            try:
                lessons.extend(get_rest_lessons(self.session, chunk_start, chunk_end))
            except (RestTimetableError, requests.RequestException) as err:
                _LOGGER.debug("REST timetable not available for exams: %s", err)
                return []
            except Exception:
                # Optional data source: never let it break the integration setup
                _LOGGER.warning(
                    "Unexpected error reading exams from the REST timetable",
                    exc_info=True,
                )
                return []
            chunk_start = chunk_end + timedelta(days=1)

        event_list = []
        for lesson in lessons:
            if not lesson["is_exam"]:
                continue
            subject = lesson["subjects"][0]["name"] if lesson["subjects"] else ""
            teacher = ", ".join(t["name"] for t in lesson["teachers"])
            summary = (
                get_lesson_name_str(self.server, subject, teacher)
                if subject
                else lesson["name"] or "Exam"
            )
            # lessonInfo is usually repeated in texts; keep each text once
            description = "\n".join(
                dict.fromkeys(
                    text
                    for text in (
                        lesson["name"],
                        lesson["lesson_info"],
                        lesson["lesson_text"],
                        *lesson["texts"],
                    )
                    if text
                )
            )
            event_list.append(
                CalendarEvent(
                    uid=str(uuid.uuid4()),
                    summary=summary,
                    start=datetime.fromisoformat(lesson["start"]),
                    end=datetime.fromisoformat(lesson["end"]),
                    description=description or None,
                    location=", ".join(r["long_name"] for r in lesson["rooms"]) or None,
                )
            )
        return event_list

    def _process_exam_data(self, response_data):
        """
        Process the exam response data and return a list of event dictionaries.
        """
        exams = response_data.get("data", {}).get("exams", [])

        event_list = []

        # Process each exam entry and create a CalendarEvent object
        for exam in exams:
            try:
                exam_id = exam.get("id", None)
                exam_type = exam.get("examType", "Unknown Type")
                name = exam.get("name", "No Name")
                subject = exam.get("subject", "Unknown Subject")
                text = exam.get("text", "")

                assigned_students = exam.get("assignedStudents", [])
                if assigned_students:  # Checks if the list is not empty
                    student_id = assigned_students[0].get("id", None)
                else:
                    student_id = None

                # Parse dates and times for the exam
                exam_date = exam.get("examDate")
                start_time = exam.get("startTime", 0)
                end_time = exam.get("endTime", 0)

                # Combine date and time for start and end datetime objects, ensuring they are timezone-aware
                start_datetime = parse_datetime(
                    date=exam_date, time=start_time
                ).astimezone()

                end_datetime = parse_datetime(
                    date=exam_date, time=end_time
                ).astimezone()

                if end_datetime < start_datetime:
                    # Log a warning if the end datetime is before the start datetime
                    print(
                        f"Warning: Exam ID {exam_id} has an end datetime before the start datetime. Skipping this entry."
                    )
                    continue

                # Get teacher and room details
                teachers = ", ".join(exam.get("teachers", [])) or "Unknown Teacher"
                rooms = ", ".join(exam.get("rooms", [])) or "Unknown Room"

                summary = get_lesson_name_str(self.server, subject, teachers)

                description = f"""{exam_type} Name: {name}"""

                if text:
                    description += f" Text: \n{text}"

                # Create a structured CalendarEvent object with timezone-aware datetimes
                event = {
                    "uid": str(uuid.uuid4()),
                    "summary": summary,
                    "start": start_datetime,
                    "end": end_datetime,
                    "description": description,
                    "location": rooms,
                }

                if (
                    self.server.student_id is None
                    or self.server.student_id == student_id
                ):
                    event_list.append(CalendarEvent(**event))
            except Exception as e:
                # Log the error and continue processing other exam entries
                print(f"Error processing exam entry: {exam}. Error: {e!s}")
                continue

        return event_list


# Example usage:
def return_exam_events(server, timezone_str="UTC"):
    """
    Function to initialize the ExamEventsFetcher class and return the exam events.
    """
    fetcher = ExamEventsFetcher(server, timezone_str=timezone_str)
    return fetcher._get_exam_events()
