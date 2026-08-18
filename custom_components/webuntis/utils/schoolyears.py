"""Helpers for working with WebUntis schoolyears."""

from __future__ import annotations

from datetime import date
from typing import Any


def resolve_schoolyear(schoolyears: Any):
    """Return a usable schoolyear without relying on WebUntis' broken current property.

    Preference order:
    1. A schoolyear that contains today's date.
    2. The next future schoolyear, for summer holiday gaps.
    3. The most recent past schoolyear, as a last resort.
    """

    if not schoolyears:
        return None

    today = date.today()
    schoolyear_list = list(schoolyears)
    current_schoolyears = []
    future_schoolyears = []
    past_schoolyears = []

    for schoolyear in schoolyear_list:
        try:
            start = schoolyear.start.date()
            end = schoolyear.end.date()
        except Exception:
            continue

        if start <= today <= end:
            current_schoolyears.append(schoolyear)
        elif start > today:
            future_schoolyears.append(schoolyear)
        else:
            past_schoolyears.append(schoolyear)

    if current_schoolyears:
        return sorted(current_schoolyears, key=lambda item: item.start)[0]

    if future_schoolyears:
        return sorted(future_schoolyears, key=lambda item: item.start)[0]

    if past_schoolyears:
        return sorted(past_schoolyears, key=lambda item: item.end)[-1]

    return schoolyear_list[0] if schoolyear_list else None
