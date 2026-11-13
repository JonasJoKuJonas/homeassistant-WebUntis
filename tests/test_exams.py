"""Offline exam regression tests with synthetic Untis data only.

The integration has no HA test harness. Stub only its calendar/datetime boundary;
load the real utility modules and use the pinned webuntis SubjectList API.
"""

import importlib
import sys
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest
import requests
import webuntis
from webuntis.objects import SubjectList


@pytest.fixture
def exams_module(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    for name, path in (
        ("exam_test_component", root / "custom_components/webuntis"),
        ("exam_test_component.utils", root / "custom_components/webuntis/utils"),
    ):
        module = ModuleType(name)
        module.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, module)

    @dataclass
    class CalendarEvent:
        summary: str
        start: datetime
        end: datetime
        uid: str = ""
        description: str | None = None
        location: str | None = None

    for name in (
        "homeassistant",
        "homeassistant.components",
        "homeassistant.components.calendar",
        "homeassistant.util",
        "homeassistant.util.dt",
    ):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    sys.modules["homeassistant.components.calendar"].CalendarEvent = CalendarEvent
    dt = sys.modules["homeassistant.util.dt"]
    dt.now = lambda: datetime(2026, 11, 13, tzinfo=UTC)
    dt.as_local = lambda value: value.replace(tzinfo=UTC)
    monkeypatch.setattr(sys.modules["homeassistant.util"], "dt", dt, raising=False)
    module = importlib.import_module("exam_test_component.utils.exams")
    yield module
    for name in list(sys.modules):
        if name.startswith("exam_test_component."):
            monkeypatch.delitem(sys.modules, name, raising=False)


@pytest.fixture
def server():
    subjects = SubjectList(
        session=SimpleNamespace(),
        data=[
            {"id": 101, "name": "SYN", "longName": "Synthetic Subject"},
        ],
    )
    return SimpleNamespace(
        session=SimpleNamespace(subjects=Mock(return_value=subjects)),
        current_schoolyear=None,
        student_id=None,
        lesson_long_name=True,
        lesson_replace_name={},
        lesson_add_teacher=[],
    )


def events(module, server, path, monkeypatch, subject="SYN", count=1):
    fetcher = module.ExamEventsFetcher(server)
    if path == "api":
        exam = {
            "subject": subject,
            "examDate": 20261113,
            "startTime": 900,
            "endTime": 1000,
            "teachers": ["T1", "T2"],
        }
        return fetcher._process_exam_data({"data": {"exams": [exam] * count}})
    lesson = {
        "is_exam": True,
        "subjects": [{"id": 101, "name": subject}],
        "teachers": [{"name": "T1"}, {"name": "T2"}],
        "name": "Synthetic exam",
        "lesson_info": "",
        "lesson_text": "",
        "texts": [],
        "rooms": [],
        "start": "2026-11-13T09:00:00+00:00",
        "end": "2026-11-13T10:00:00+00:00",
    }
    monkeypatch.setattr(module, "get_rest_lessons", lambda *a, **kw: [lesson] * count)
    return fetcher._get_rest_exam_events(date(2026, 8, 1), date(2027, 7, 31))


@pytest.mark.parametrize("path", ["api", "rest"])
def test_exam_titles_use_untis_subject_long_names(
    exams_module, server, path, monkeypatch
):
    result = events(exams_module, server, path, monkeypatch)
    assert [event.summary for event in result] == ["Synthetic Subject"]


@pytest.mark.parametrize("path", ["api", "rest"])
@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("replacement", [False, True])
@pytest.mark.parametrize("teacher", [False, True])
def test_short_name_options_remain_compatible(
    exams_module, server, path, enabled, replacement, teacher, monkeypatch
):
    server.lesson_long_name = enabled
    server.lesson_replace_name = {"SYN": "Custom title"} if replacement else {}
    server.lesson_add_teacher = ["SYN"] if teacher else []
    expected = (
        "Custom title" if replacement else ("Synthetic Subject" if enabled else "SYN")
    )
    if teacher:
        expected += " - T1, T2"
    assert events(exams_module, server, path, monkeypatch)[0].summary == expected
    if not enabled:
        server.session.subjects.assert_not_called()


@pytest.mark.parametrize("path", ["api", "rest"])
@pytest.mark.parametrize(
    "data",
    [
        [],
        [{"id": 102, "name": "OTHER", "longName": "Other Subject"}],
        [{"id": 101, "name": "SYN"}],
        [{"id": 101, "name": "SYN", "longName": ""}],
        [{"id": 101, "name": "SYN", "longName": None}],
    ],
)
def test_missing_subject_master_data_preserves_original_text(
    exams_module, server, path, data, monkeypatch
):
    server.session.subjects.return_value = SubjectList(
        session=SimpleNamespace(), data=data
    )
    assert events(exams_module, server, path, monkeypatch)[0].summary == "SYN"


@pytest.mark.parametrize("path", ["api", "rest"])
@pytest.mark.parametrize(
    "error",
    [
        webuntis.errors.RemoteError("no right"),
        requests.ConnectionError("offline"),
    ],
)
def test_subject_lookup_failure_is_optional_and_not_retried_per_exam(
    exams_module, server, path, error, monkeypatch
):
    server.session.subjects.side_effect = error
    server.lesson_add_teacher = ["SYN"]
    result = events(exams_module, server, path, monkeypatch, count=3)
    assert [event.summary for event in result] == ["SYN - T1, T2"] * 3
    server.session.subjects.assert_called_once_with(from_cache=True)


@pytest.mark.parametrize("path", ["api", "rest"])
def test_subject_list_is_fetched_once_for_multiple_exams(
    exams_module, server, path, monkeypatch
):
    result = events(exams_module, server, path, monkeypatch, count=4)
    assert [event.summary for event in result] == ["Synthetic Subject"] * 4
    server.session.subjects.assert_called_once_with(from_cache=True)


@pytest.mark.parametrize("path", ["api", "rest"])
def test_long_name_replacement_keeps_short_name_teacher_selection(
    exams_module, server, path, monkeypatch
):
    server.lesson_replace_name = {"Synthetic Subject": "Custom long title"}
    server.lesson_add_teacher = ["SYN"]
    assert events(exams_module, server, path, monkeypatch)[0].summary == (
        "Custom long title - T1, T2"
    )


def test_existing_library_subject_cache_avoids_network(exams_module, server):
    session = webuntis.Session(server="https://example.invalid", school="synthetic")
    session._request = Mock(
        return_value=[
            {"id": 101, "name": "SYN", "longName": "Synthetic Subject"},
        ]
    )
    session.subjects()  # Prime the same master-data cache used by normal lessons.
    session._request.reset_mock()
    server.session = session
    fetcher = exams_module.ExamEventsFetcher(server)
    assert fetcher._get_exam_summary("SYN", "T1") == "Synthetic Subject"
    session._request.assert_not_called()


def test_both_sources_share_subject_lookup(exams_module, server, monkeypatch):
    server.schoolyears = [
        SimpleNamespace(start=datetime(2026, 8, 1), end=datetime(2027, 7, 31))
    ]
    server.session.get_exams = Mock(
        return_value={
            "data": {
                "exams": [
                    {
                        "subject": "SYN",
                        "examDate": 20261113,
                        "startTime": 900,
                        "endTime": 1000,
                        "teachers": ["T1"],
                    }
                ]
            }
        }
    )
    lesson = {
        "is_exam": True,
        "subjects": [{"id": 101, "name": "SYN"}],
        "teachers": [],
        "name": "Synthetic exam",
        "lesson_info": "",
        "lesson_text": "",
        "texts": [],
        "rooms": [],
        "start": "2026-11-14T09:00:00+00:00",
        "end": "2026-11-14T10:00:00+00:00",
    }
    monkeypatch.setattr(exams_module, "get_rest_lessons", Mock(return_value=[lesson]))
    result = exams_module.ExamEventsFetcher(server)._get_exam_events()
    assert [event.summary for event in result] == ["Synthetic Subject"] * 2
    server.session.subjects.assert_called_once_with(from_cache=True)
    exams_module.get_rest_lessons.assert_called_once()


@pytest.mark.parametrize(
    "name, expected", [("Synthetic exam", "Synthetic exam"), ("", "Exam")]
)
def test_rest_exam_without_subject_retains_name_fallback(
    exams_module, server, monkeypatch, name, expected
):
    lesson = {
        "is_exam": True,
        "subjects": [],
        "teachers": [],
        "name": name,
        "lesson_info": "",
        "lesson_text": "",
        "texts": [],
        "rooms": [],
        "start": "2026-11-13T09:00:00+00:00",
        "end": "2026-11-13T10:00:00+00:00",
    }
    monkeypatch.setattr(exams_module, "get_rest_lessons", Mock(return_value=[lesson]))
    result = exams_module.ExamEventsFetcher(server)._get_rest_exam_events(
        date(2026, 8, 1), date(2027, 7, 31)
    )
    assert [event.summary for event in result] == [expected]
    server.session.subjects.assert_not_called()


def test_api_exam_without_subject_retains_original_fallback(exams_module, server):
    result = exams_module.ExamEventsFetcher(server)._process_exam_data(
        {
            "data": {
                "exams": [
                    {
                        "examDate": 20261113,
                        "startTime": 900,
                        "endTime": 1000,
                    }
                ]
            }
        }
    )
    assert [event.summary for event in result] == ["Unknown Subject"]
