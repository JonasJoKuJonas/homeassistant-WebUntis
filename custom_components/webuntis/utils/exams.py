import uuid
from webuntis import errors
from homeassistant.components.calendar import CalendarEvent
from webuntis.utils.datetime_utils import parse_datetime


# pylint: disable=relative-beyond-top-level
from ..utils.web_untis import get_lesson_name_str


class ExamEventsFetcher:
    def __init__(self, server, current_schoolyear, timezone_str="UTC"):
        self.server = server
        self.session = server.session
        self.event_list = []
        self.current_schoolyear = current_schoolyear

    def _get_exam_events(self):
        """
        Fetch exam events from the WebUntis API using the session object and return them as a list of event dictionaries.
        """

        # Fetch exam data using the session object
        try:
            exam_data = self.session.get_exams(
                start=self.current_schoolyear.start,
                end=self.current_schoolyear.end,
            )
        except errors.NotLoggedInError:
            raise Exception("You are not logged in. Please log in and try again.")
        except errors.RemoteError as e:
            raise Exception(f"Error fetching exam data: {e}")

        # Process the exam data and extract exam events
        exam_events = self._process_exam_data(exam_data)
        return exam_events

    def _process_exam_data(self, response_data):
        """
        Process the exam response data and return a list of event dictionaries.
        """
        exams = response_data.get("data", {}).get("exams", [])

        event_list = []

        # Process each exam entry and create a CalendarEvent object
        for exam in exams:
            exam_id = exam.get("id", None)
            exam_type = exam.get("examType", "Unknown Type")
            name = exam.get("name", "No Name")
            subject = exam.get("subject", "Unknown Subject")
            text = exam.get("text", "")
            grade = exam.get("grade", "")
            student_id = exam.get("assignedStudents", [])[0].get("id", None)

            # Parse dates and times for the exam
            exam_date = exam.get("examDate")
            start_time = exam.get("startTime", 0)
            end_time = exam.get("endTime", 0)

            # Combine date and time for start and end datetime objects, ensuring they are timezone-aware
            start_datetime = parse_datetime(
                date=exam_date, time=start_time
            ).astimezone()

            end_datetime = parse_datetime(date=exam_date, time=end_time).astimezone()

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

            if self.server.student_id is None or self.server.student_id == student_id:
                event_list.append(CalendarEvent(**event))

        return event_list


# Example usage:
def return_exam_events(server, current_schoolyear, timezone_str="UTC"):
    """
    Function to initialize the ExamEventsFetcher class and return the exam events.
    """
    fetcher = ExamEventsFetcher(server, current_schoolyear, timezone_str)
    return fetcher._get_exam_events()
