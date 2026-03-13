"""Miscellaneous support functions for webuntis"""

import copy
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
            compacted_list.append(
                [item[0], copy.deepcopy(item[1]), copy.deepcopy(item[2])]
            )
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
            compacted_list.append(copy.deepcopy(item))
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
            compacted_list.append(copy.deepcopy(item))
            i += 1

    return compacted_list


async def async_notify(hass, service_id, data):
    """Show a notification."""

    if not isinstance(data, dict):
        data = {}

    data = copy.deepcopy(data)

    if "target" in data and not data["target"]:
        del data["target"]

    domain, service = service_id.split(".", 1)

    target_arg = None
    if domain == "notify" and service == "send_message":
        # Flatten nested `data` payloads that some automations may create.
        nested = data.pop("data", None)
        if isinstance(nested, dict):
            for k, v in nested.items():
                data.setdefault(k, v)

        # Move target out of the payload and into the service target argument.
        if "target" in data:
            raw_target = data.pop("target")
            if isinstance(raw_target, str):
                target_arg = {"entity_id": [raw_target]}
            elif isinstance(raw_target, (list, tuple)):
                target_arg = {"entity_id": list(raw_target)}
            else:
                target_arg = raw_target

    _LOGGER.debug(
        "Send notification(%s): service_data=%s target=%s",
        service_id,
        data,
        target_arg if target_arg is not None else data.get("target"),
    )

    try:
        await hass.services.async_call(
            domain,
            service,
            service_data=data,
            target=target_arg,
            blocking=True,
        )
    except Exception as error:
        _LOGGER.warning(
            "Sending notification to %s failed - %s",
            service_id,
            error,
        )
        return False

    return True
