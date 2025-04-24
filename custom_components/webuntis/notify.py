from .const import TEMPLATE_OPTIONS

from .utils.web_untis import get_lesson_name_str


def compare_list(old_list, new_list, blacklist=[]):
    updated_items = []

    for new_item in new_list:
        for old_item in old_list:
            if (
                new_item["subject_id"] == old_item["subject_id"]
                and new_item["start"] == old_item["start"]
                and not (
                    new_item["code"] == "irregular" and old_item["code"] == "cancelled"
                )
            ):
                # if lesson is on blacklist to prevent spaming notifications
                if any(
                    item["subject_id"] == new_item["subject_id"]
                    and item["start"] == new_item["start"]
                    for item in blacklist
                ):
                    break

                if new_item["code"] != old_item["code"]:
                    if old_item["code"] == "None" and new_item["code"] == "cancelled":
                        matching_item = next(
                            (
                                item
                                for item in new_list
                                if item["start"] == new_item["start"]
                                and item["subject_id"] != new_item["subject_id"]
                                and item["code"] == "irregular"
                            ),
                            None,
                        )

                        if matching_item is not None:
                            updated_items.append(
                                ["lesson_change", matching_item, old_item]
                            )
                        else:
                            updated_items.append(["cancelled", new_item, old_item])
                    else:
                        updated_items.append(["code", new_item, old_item])

                if (
                    "rooms" in new_item
                    and "rooms" in old_item
                    and new_item["rooms"]
                    and old_item["rooms"]
                    and new_item["rooms"] != old_item["rooms"]
                    and new_item["code"] != "cancelled"
                ):
                    updated_items.append(["rooms", new_item, old_item])

                if (
                    "teachers" in new_item
                    and "teachers" in old_item
                    and new_item["teachers"]
                    and old_item["teachers"]
                    and new_item["teachers"] != old_item["teachers"]
                    and new_item["code"] != "cancelled"
                ):
                    updated_items.append(["teachers", new_item, old_item])

                break

    return updated_items


def get_notify_blacklist(current_list):
    blacklist = []

    for item in compare_list(current_list, current_list):
        blacklist.append(
            {"subject_id": item[1]["subject_id"], "start": item[1]["start"]}
        )

    return blacklist


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
<b>WebUntis ({entry_title}) - {changes['title']}</b>
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
        "lesson_change": "Lesson changed",
        "teachers": "Teacher changed",
    }[change]

    changes["subject"] = generate_lesson_name(lesson, server)

    changes["date"] = lesson["start"].strftime("%d.%m.%Y")
    changes["time_start"] = lesson["start"].strftime("%H:%M")
    changes["time_end"] = lesson["end"].strftime("%H:%M")

    changes["old"] = None
    changes["new"] = None

    if change == "cancelled":
        pass
    elif change == "lesson_change":
        changes.update(
            {
                "old": lesson_old.get("subjects", [{}])[0].get("long_name", ""),
                "new": lesson.get("subjects", [{}])[0].get("long_name", ""),
            }
        )
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


def generate_lesson_name(lesson, server):
    try:
        if server.lesson_long_name:
            name = lesson["subjects"][0]["long_name"]
        else:
            name = lesson["subjects"][0]["name"]
    except IndexError:
        name = "None"

    teacher = None
    if "teachers" not in server.exclude_data:
        try:
            teacher = lesson["teachers"][0]["name"]
        except IndexError:
            pass

    return get_lesson_name_str(server, name, teacher)
