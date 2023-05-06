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
