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
                # test if lesson is on blacklist to prevent spaming notifications
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
                                ["lesson change", matching_item, old_item]
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
                ):
                    updated_items.append(["rooms", new_item, old_item])

                break

    return updated_items


def get_notification(updated_items, notify_list):
    notify = []

    updated_items = [item for item in updated_items if item[0] in notify_list]

    for change, lesson, lesson_old in updated_items:
        title = "WebUntis"
        title += (
            " - "
            + {
                "code": "Status changed",
                "rooms": "Room changed",
                "cancelled": "Lesson cancelled",
                "lesson change": "Lesson changed",
            }[change]
        )

        message = ""
        try:
            message += f"Subject: {lesson['subjects'][0]['long_name']}\n"
        except IndexError:
            pass

        message += f"Date: {lesson['start'].strftime('%d.%m.%Y')}\n"
        message += f"Time: {lesson['start'].strftime('%H:%M')} - {lesson['end'].strftime('%H:%M')}\n"

        if change == "cancelled":
            pass
        elif change == "lesson change":
            message += f"Change (Lesson): {lesson_old['subjects'][0]['long_name']} -> {lesson['subjects'][0]['long_name']}"

        elif change == "rooms":
            try:
                message += f"Change (Room): {lesson_old['rooms'][0]['name']} -> {lesson['rooms'][0]['name']}"
            except KeyError:
                pass

        else:
            message += f"Change ({change}): {lesson_old[change]} -> {lesson[change]}"

        notify.append({"title": title, "message": message})

    return notify


def get_notify_blacklist(current_list):
    blacklist = []

    for item in compare_list(current_list, current_list):
        blacklist.append(
            {"subject_id": item[1]["subject_id"], "start": item[1]["start"]}
        )

    return blacklist
