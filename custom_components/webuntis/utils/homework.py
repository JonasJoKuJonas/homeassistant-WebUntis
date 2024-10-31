from datetime import date, timedelta, datetime
from webuntis import errors
import pytz  # to handle timezone conversions

from homeassistant.components.calendar import CalendarEvent

from custom_components.webuntis.const import DAYS_TO_CHECK

# pylint: disable=relative-beyond-top-level
from ..utils.web_untis import get_lesson_name_str


class HomeworkEventsFetcher:
    def __init__(
        self,
        server,
        calendar_description="Lesson Info",
        calendar_room="Room long name",
        timezone="Europe/Berlin",  # Default timezone, can be changed if needed
    ):
        self.session = server.session
        self.server = server
        self.calendar_description = calendar_description
        self.calendar_room = calendar_room
        self.event_list = []
        self.timezone = pytz.timezone(timezone)

    def _get_homework_events(self):
        """
        Fetch homework events from the WebUntis API and return them as a list of calendar events.
        """
        today = date.today()
        start = today - timedelta(days=DAYS_TO_CHECK)
        end = today + timedelta(days=DAYS_TO_CHECK)

        # Fetch homework data using the session object
        try:
            homework_data = self.session.get_homeworks(
                start=start,
                end=end,
            )
        except errors.NotLoggedInError:
            raise Exception("You are not logged in. Please log in and try again.")

        # Process the homework data and extract the homework events
        homework_events = self._process_homework_data(homework_data)
        return homework_events

    def _process_homework_data(self, response_data):
        """
        Process the homework response data and return a list of event dictionaries.
        """
        homeworks = response_data.get("data", {}).get("homeworks", [])
        lessons = response_data.get("data", {}).get("lessons", [])
        records = response_data.get("data", {}).get("records", [])
        teachers = response_data.get("data", {}).get("teachers", [])

        # Create a mapping of teacher ID to teacher data
        teacher_map = {teacher["id"]: teacher for teacher in teachers}

        event_list = []
        param_list = []

        # Process each homework entry
        for homework in homeworks:
            hw_id = homework.get("id")
            lesson_id = homework.get("lessonId")
            date_assigned_int = homework.get("date")  # Date in integer YYYYMMDD format
            due_date_int = homework.get(
                "dueDate"
            )  # Due date in integer YYYYMMDD format
            text = homework.get("text")
            completed = homework.get("completed", False)

            date_assigned = datetime.strptime(str(date_assigned_int), "%Y%m%d").date()
            due_date = datetime.strptime(
                str(due_date_int), "%Y%m%d"
            ).date() + timedelta(days=1)

            # Find the corresponding record to get the teacher ID
            record = next((rec for rec in records if rec["homeworkId"] == hw_id), None)

            # Fetch the teacher ID from the record
            teacher_id = record.get("teacherId") if record else None

            student_id = record.get("elementIds", [])[0]

            # Get the teacher's name using the teacher ID
            teacher = teacher_map.get(teacher_id, {})
            teacher_name = teacher.get("name", "Unknown Teacher")

            # Find the corresponding lesson
            lesson = next((l for l in lessons if l["id"] == lesson_id), {})
            subject = lesson.get("subject", "Unknown Subject")

            summary = get_lesson_name_str(self.server, subject, teachers[0]["name"])

            # Create a calendar event for each homework entry
            event = {
                "uid": hw_id,
                "summary": summary,
                "start": date_assigned,
                "end": due_date,
                "description": text,
            }

            parameters = {
                "homework_id": hw_id,
                "subject": subject,
                "teacher": teacher_name,
                "student_id": student_id,
                "completed": completed,
                "date_assigned": date_assigned,
                "due_date": due_date,
                "text": text,
            }

            if self.server.student_id is None or self.server.student_id == student_id:
                # Add the homework event to the event list
                event_list.append(CalendarEvent(**event))

                param_list.append(parameters)

        return event_list, param_list


# Example usage:
def return_homework_events(server):
    fetcher = HomeworkEventsFetcher(server)
    return fetcher._get_homework_events()
