"""Miscellaneous support functions for webuntis"""


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


def compact_list(lst, type=None):
    if type == "notify":
        compacted_list = []
        i = 0
        while i < len(lst):
            item = lst[i]
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

    else:
        compacted_list = []
        i = 0
        while i < len(lst):
            item = lst[i]
            if compacted_list:
                last_item = compacted_list[-1]
                if last_item.end == item.start and last_item.summary == item.summary:
                    last_item.end = item.end

                    i += 1
                    continue
            compacted_list.append(item)
            i += 1

    return compacted_list
