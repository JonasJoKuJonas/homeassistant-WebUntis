from .const import TEMPLATE_OPTIONS

from .utils.web_untis import get_lesson_name_str, get_lesson_name


def compare_timetables(old_timetable, new_timetable) -> list:
    updated_items = []
    
    # Create a dictionary for lookup of old lessons
    # Using (lsnumber, start) as the key for matching
    old_lessons_map = {
        (lesson["lsnumber"], lesson["start"]): lesson 
        for lesson in old_timetable
    }
    
    for new_lesson in new_timetable:
        # Look up the corresponding old lesson using the key
        key = (new_lesson["lsnumber"], new_lesson["start"])
        
        if key not in old_lessons_map:
            continue
        
        old_lesson = old_lessons_map[key]
        
        # if compared lessons are the same
        if new_lesson == old_lesson:
            continue

        checked_fields = [
            "rooms",
            "subject_id",
            "subjects",
            "teachers",
            "lstext",
            "code",
            "info",
        ]

        # compare lesson rooms
        if new_lesson.get("code", "None") != "cancelled":
            if (
                (
                    "rooms" in new_lesson
                    and "rooms" in old_lesson
                    and new_lesson["rooms"]
                    and old_lesson["rooms"]
                    and new_lesson["rooms"] != old_lesson["rooms"] 
                ) or (
                    "rooms" not in new_lesson
                    and "rooms" in old_lesson
                    and old_lesson["rooms"]
                )
            ):
                updated_items.append(["rooms", new_lesson, old_lesson])

        # compare lesson subject
        if (
            "subject_id" in new_lesson
            and "subject_id" in old_lesson
            and new_lesson["subject_id"]
            and old_lesson["subject_id"]
            and new_lesson["subject_id"] != old_lesson["subject_id"]
        ):
            updated_items.append(["subject", new_lesson, old_lesson])

        # compare lesson teachers
        if new_lesson.get("code", "None") != "cancelled":
            if (
                (
                    "teachers" in new_lesson
                    and "teachers" in old_lesson
                    and new_lesson["teachers"]
                    and old_lesson["teachers"]
                    and new_lesson["teachers"] != old_lesson["teachers"]
                ) or (
                    "teachers" not in new_lesson
                    and "teachers" in old_lesson
                    and old_lesson["teachers"]
                )
            ):
                updated_items.append(["teachers", new_lesson, old_lesson])

        # compare lesson text
        old_lstext = old_lesson.get("lstext", "") or ""
        new_lstext = new_lesson.get("lstext", "") or ""
        if new_lstext != old_lstext:
            updated_items.append(["lstext", new_lesson, old_lesson])
        
        # compare lesson info (text that the teacher wrote for students)
        old_info = old_lesson.get("info", "") or ""
        new_info = new_lesson.get("info", "") or ""
        if new_info != old_info:
            updated_items.append(["info", new_lesson, old_lesson])

        # compare lesson code
        old_code = old_lesson.get("code", "None")
        new_code = new_lesson.get("code", "None")

        if new_code != old_code:
            if old_code == "None" and new_code == "cancelled":
                updated_items.append(["cancelled", new_lesson, old_lesson])
            elif old_code == "None" and new_code == "irregular":
                updated_items.append(["code", new_lesson, old_lesson])
            else:
                updated_items.append(["code", new_lesson, old_lesson])

    return updated_items


def get_notification_data(changes, service, entry_title):

    message = ""
    title = ""
    data = {}
    result = {}

    template = service.get("template", TEMPLATE_OPTIONS[0])

    if template == "message_title" or template == "message":
        title = f"WebUntis ({entry_title}) - {changes['title']}"
        result["title"] = title
        message = f"""Subject: {changes["subject"]}
Date: {changes["date"]}
Time: {changes["time_start"]} - {changes["time_end"]}"""

        if changes["change"] not in ["cancelled", "test"]:
            message += f"""
Change ({changes["change"]}):
Old: {changes["old"]}
New: {changes["new"]}"""

    if template == "message":
        message = f"{title}\n{message}"
        result.pop("title")

    if template == "telegram":
        message = f"""
<b>WebUntis ({entry_title}) - {changes["title"]}</b>
<b>Subject:</b> {changes["subject"]}
<b>Date:</b> {changes["date"]}
<b>Time:</b> {changes["time_start"]} - {changes["time_end"]}"""

        if changes["change"] not in ["cancelled", "test"]:
            message += f"""
<b>{changes["change"]}</b>
<b>Old:</b> {changes["old"]}
<b>New:</b> {changes["new"]}"""
        data = {"parse_mode": "html"}

    if template == "discord":
        data = {
            "embed": {
                "title": changes["title"],
                "description": entry_title,
                "color": 16750848,
                "author": {
                    "name": "WebUntis",
                    "url": "https://www.home-assistant.io",
                    "icon_url": "https://brands.home-assistant.io/webuntis/icon.png",
                },
                "fields": [
                    {"name": "Subject", "value": changes["subject"], "inline": False},
                    {"name": "Date", "value": changes["date"], "inline": False},
                    {"name": "Time", "value": "", "inline": False},
                    {"name": "Start", "value": changes["time_start"]},
                    {"name": "End", "value": changes["time_end"]},
                ],
            }
        }

        if changes["change"] not in ["cancelled", "test"]:
            data["embed"]["fields"].extend(
                [
                    {
                        "name": changes["title"].replace(" changed", ""),
                        "value": "",
                        "inline": False,
                    },
                    {"name": "Old", "value": changes["old"]},
                    {"name": "New", "value": changes["new"]},
                ]
            )

    result["message"] = message

    return result, data


"""
parameters = {
    "homework_id": hw_id,
    "subject": subject,
    "teacher": teacher_name,
    "completed": completed,
    "date_assigned": date_assigned,
    "due_date": due_date,
    "text": text,
}
"""


def get_notification_data_homework(parameters, service, entry_title, server):
    message = ""
    title = ""
    data = {}

    subject = get_lesson_name_str(server, parameters["subject"], parameters["teacher"])

    template = service.get("template", TEMPLATE_OPTIONS[0])

    if template == "message_title":
        title = f"WebUntis ({entry_title}) - Homework: {subject}"
        message = f"""{parameters["text"]}
Subject: {parameters["subject"]}
Teacher: {parameters["teacher"]}
Assigned Date: {parameters["date_assigned"]}
Due Date: {parameters["due_date"]}"""

    elif template == "message":
        message = f"{title}\n{message}"

    elif template == "discord":
        data = {
            "embed": {
                "title": "Homework: " + subject,
                "description": entry_title,
                "color": 16750848,
                "author": {
                    "name": "WebUntis",
                    "url": "https://www.home-assistant.io",
                    "icon_url": "https://brands.home-assistant.io/webuntis/icon.png",
                },
                "fields": [
                    {
                        "name": "Subject",
                        "value": subject,
                        "inline": False,
                    },
                    {
                        "name": "Text",
                        "value": parameters["text"],
                        "inline": False,
                    },
                    {"name": "Date", "value": "", "inline": False},
                    {"name": "Assigned", "value": parameters["date_assigned"]},
                    {"name": "Due", "value": parameters["due_date"]},
                ],
            }
        }

    return {
        "message": message,
        "title": title,
    }, data


def get_changes(change, lesson, lesson_old, server):

    changes = {"change": change}

    changes["title"] = {
        "code": "Status changed",
        "rooms": "Room changed",
        "cancelled": "Lesson cancelled",
        "teachers": "Teacher changed",
        "lstext": "Lesson text changed",
        "subject": "Subject changed",
        "info": "Info text changed"
    }[change]

    changes["subject"] = get_lesson_name(server, lesson)

    changes["date"] = lesson["start"].strftime("%d.%m.%Y")
    changes["time_start"] = lesson["start"].strftime("%H:%M")
    changes["time_end"] = lesson["end"].strftime("%H:%M")

    changes["old"] = None
    changes["new"] = None

    if change == "subject":
        old_subjects = lesson_old.get("subjects")
        if old_subjects and len(old_subjects) > 0:
            changes["old"] = old_subjects[0].get("long_name", "")
        else:
            changes["old"] = ""
        new_subjects = lesson.get("subjects")
        if new_subjects and len(new_subjects) > 0:
            changes["new"] = new_subjects[0].get("long_name", "")
        else:
            changes["new"] = ""
    elif change == "lstext":
        changes["old"] = lesson_old.get("lstext", "")
        changes["new"] = lesson.get("lstext", "")
    elif change == "info":
        changes["old"] = lesson_old.get("info", "")
        changes["new"] = lesson.get("info", "")
    elif change == "rooms":
        changes.update(
            {
                "old": lesson_old.get("rooms", [{}])[0].get("name", ""),
                "new": lesson.get("rooms", [{}])[0].get("name", ""),
            }
        )
    elif change == "teachers":
        changes.update(
            {
                "old": lesson_old.get("teachers", [{}])[0].get("name", ""),
                "new": lesson.get("teachers", [{}])[0].get("name", ""),
            }
        )

    return changes
