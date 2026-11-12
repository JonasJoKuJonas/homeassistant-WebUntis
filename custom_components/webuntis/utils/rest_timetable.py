"""Timetable access via the WebUntis REST API used by the web and mobile apps.

The JSON-RPC API does not expose exams that are only attached to a lesson
(shown as "Prüfung" in the app) and misses newer lesson information texts.
The REST timetable endpoint returns both, so it is used to fill those gaps.
"""

from __future__ import annotations

import logging
from datetime import date, datetime

import requests
from homeassistant.util import dt as dt_util

from .rest_api import REQUEST_TIMEOUT, RestApiError, auth_headers, base_url, cookies

_LOGGER = logging.getLogger(__name__)

TIMETABLE_ENDPOINT = "/WebUntis/api/rest/view/v1/timetable/entries"

# JSON-RPC person types (login_result["personType"]) -> REST resource types
RESOURCE_TYPES = {
    2: "TEACHER",
    5: "STUDENT",
    12: "STUDENT",
}  # 12 is parent which also access the student timetable


# Kept as a name for callers that catch timetable errors
RestTimetableError = RestApiError


def fetch_rest_timetable(
    session, start: date, end: date, resource_id: int | None = None
) -> dict:
    """Return the raw REST timetable response for the logged-in person."""
    login_result = getattr(session, "login_result", None) or {}
    person_type = login_result.get("personType")
    person_id = login_result.get("personId")
    if not isinstance(person_type, int) or not isinstance(person_id, int):
        raise RestTimetableError("No valid login result found, please log in first")
    resource_type = RESOURCE_TYPES.get(person_type)
    if resource_type is None:
        raise RestTimetableError(
            f"Unsupported account for REST timetable (personType={person_type})"
        )
    if person_type == 12:
        if not isinstance(resource_id, int):
            raise RestTimetableError(
                "No student resource found for parent account"
            )
        person_id = resource_id

    headers = auth_headers(session)

    response = requests.get(
        base_url(session) + TIMETABLE_ENDPOINT,
        params={
            "start": start.isoformat(),
            "end": end.isoformat(),
            "format": 4,
            "resourceType": resource_type,
            "resources": person_id,
            "periodTypes": "",
            "timetableType": "MY_TIMETABLE",
        },
        cookies=cookies(session),
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200:
        raise RestTimetableError(
            f"Timetable request failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )
    try:
        return response.json()
    except ValueError as err:
        raise RestTimetableError("Invalid JSON in timetable response") from err


def _element(item: dict | None) -> dict | None:
    if not item:
        return None
    element = {
        "name": item.get("shortName") or item.get("displayName") or "",
        "long_name": item.get("longName") or item.get("displayName") or "",
    }
    if item.get("id") is not None:
        element["id"] = item["id"]
    return element


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


def parse_rest_timetable(data: dict) -> list[dict]:
    """Flatten the REST response into one dict per timetable entry."""
    lessons = []
    for day in data.get("days") or []:
        for entry in day.get("gridEntries") or []:
            duration = entry.get("duration") or {}
            start = _parse_time(duration.get("start"))
            end = _parse_time(duration.get("end"))
            if start is None or end is None:
                continue

            groups: dict[str, dict[str, list]] = {}
            for key, positions in entry.items():
                if not key.startswith("position") or not positions:
                    continue
                for position in positions:
                    current = position.get("current")
                    removed = position.get("removed")
                    kind = (current or removed or {}).get("type", "UNKNOWN")
                    group = groups.setdefault(kind, {"current": [], "removed": []})
                    if (el := _element(current)) is not None:
                        group["current"].append(el)
                    if (el := _element(removed)) is not None:
                        group["removed"].append(el)

            def elements(
                kind: str, which: str = "current", groups: dict = groups
            ) -> list:
                return groups.get(kind, {}).get(which, [])

            entry_type = entry.get("type") or ""
            texts = [
                text.get("text") if isinstance(text, dict) else str(text)
                for text in entry.get("texts") or []
            ]
            lessons.append(
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "type": entry_type,
                    "status": entry.get("status") or "",
                    "status_detail": entry.get("statusDetail") or "",
                    "is_exam": "EXAM" in entry_type.upper(),
                    "subjects": elements("SUBJECT"),
                    "original_subjects": elements("SUBJECT", "removed"),
                    "teachers": elements("TEACHER"),
                    "original_teachers": elements("TEACHER", "removed"),
                    "rooms": elements("ROOM"),
                    "original_rooms": elements("ROOM", "removed"),
                    "klassen": elements("CLASS"),
                    # Events without a subject (e.g. "Klassencheck") carry their label here
                    "infos": elements("INFO"),
                    "name": entry.get("name") or "",
                    "lesson_text": entry.get("lessonText") or "",
                    "lesson_info": entry.get("lessonInfo") or "",
                    "substitution_text": entry.get("substitutionText") or "",
                    "notes": entry.get("notesAll") or "",
                    "texts": [text for text in texts if text],
                }
            )
    lessons.sort(key=lambda lesson: lesson["start"])
    return lessons


def get_rest_lessons(
    session, start: date, end: date, resource_id: int | None = None
) -> list[dict]:
    """Fetch and parse the REST timetable."""
    return parse_rest_timetable(
        fetch_rest_timetable(session, start, end, resource_id=resource_id)
    )
