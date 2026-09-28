"""Helpers for working with WebUntis schoolyears."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from custom_components.webuntis import _LOGGER


def resolve_schoolyear(schoolyears: Any):
    """Return a usable schoolyear without relying on unreliable python-webuntis package.

    Preference order:
    1. A schoolyear that contains today's date
    2. The next future schoolyear, for summer holiday gaps
    3. The most recent past schoolyear
    """

    if not schoolyears:
        return None

    today = datetime.now(timezone.utc).date()
    schoolyear_list = list(schoolyears)
    current_schoolyears = []
    future_schoolyears = []
    past_schoolyears = []

    for schoolyear in schoolyear_list:
        try:
            start = schoolyear.start.date()
            end = schoolyear.end.date()
        except Exception:
            _LOGGER.warning(
                "Failed to parse schoolyear start/end dates: %s", schoolyear
            )
            continue

        if start <= today <= end:
            current_schoolyears.append(schoolyear)
        elif start > today:
            future_schoolyears.append(schoolyear)
        else:
            past_schoolyears.append(schoolyear)

    if current_schoolyears:
        return min(current_schoolyears, key=lambda item: item.start)

    if future_schoolyears:
        return min(future_schoolyears, key=lambda item: item.start)

    if past_schoolyears:
        return max(past_schoolyears, key=lambda item: item.end)

    return schoolyear_list[0] if schoolyear_list else None
