"""Miscellaneous support functions for webuntis"""

from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)


def is_service(hass, entry):
    """check whether config entry is a service"""
    domain, service = entry.split(".")[0], ".".join(entry.split(".")[1:])
    return hass.services.has_service(domain, service)


def is_different(arr1, arr2):
    """
    Compares two lists of dictionaries and returns True if they are different, False otherwise.

    Args:
    - arr1 (list): A list of dictionaries.
    - arr2 (list): A list of dictionaries.

    Returns:
    - bool: True if the two lists are different, False otherwise.
    """
    if len(arr1) != len(arr2):
        return True
    for el1 in arr1:
        found = False
        for el2 in arr2:
            if el1 == el2:
                found = True
                break
        if not found:
            return True
    return False


def compact_list(list, type=None):
    if type == "notify":
        compacted_list = []
        i = 0
        while i < len(list):
            item = list[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if (
                    last_item[2]["end"] == item[2]["start"]
                    and last_item[2]["code"] == item[2]["code"]
                ):
                    last_item[1]["end"] = item[1]["end"]
                    last_item[2]["end"] = item[2]["end"]
                    i += 1
                    continue
            compacted_list.append(item)
            i += 1

    elif type == "dict":
        compacted_list = []
        i = 0
        while i < len(list):
            item = list[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if (
                    last_item["end"] == item["start"]
                    and last_item["lsnumber"] == item["lsnumber"]
                    and last_item["code"] == item["code"]
                ):
                    last_item["end"] = item["end"]

                    i += 1
                    continue
            compacted_list.append(item)
            i += 1

    else:  # calendar
        compacted_list = []
        i = 0
        while i < len(list):
            item = list[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if last_item.end == item.start and last_item.summary == item.summary:
                    last_item.end = item.end

                    i += 1
                    continue
            compacted_list.append(item)
            i += 1

    return compacted_list


def get_schoolyear(school_year, date=datetime.now().date()):
    if not school_year:
        return None
    for time_range in school_year:
        if time_range.start.date() <= date <= time_range.end.date():
            return time_range

    return None


async def async_notify(hass, service_id, data):
    """Show a notification"""

    if "target" in data and not data["target"]:
        del data["target"]

    _LOGGER.debug("Send notification(%s): %s", service_id, data)

    domain = service_id.split(".")[0]
    service = service_id.split(".")[1]

    try:
        await hass.services.async_call(domain, service, data, blocking=True)
    except Exception as error:
        _LOGGER.warning(
            "Sending notification to %s failed - %s",
            service_id,
            error,
        )
        return False

    return True
