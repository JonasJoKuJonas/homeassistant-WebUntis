"""Helpers for WebUntis QR-code login."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse


@dataclass(frozen=True)
class QrData:
    server: str
    school: str
    user: str
    key: str
    school_number: str | None = None


qrData = QrData


def _normalize_server_url(server: str) -> str:
    parsed = urlparse(server if "://" in server else f"https://{server}")
    host = (parsed.netloc or parsed.path.split("/", 1)[0]).strip()
    if not host:
        raise ValueError("QR payload does not contain a valid server")
    return host


def parse_qr_code(payload: str) -> QrData:
    """Parse the untis:// QR payload."""
    payload = payload.strip()

    if not payload.startswith("untis://"):
        if not payload.startswith("?"):
            raise ValueError("QR payload must start with untis://")
        payload = f"untis://setschool{payload}"

    parsed_result = urlparse(payload)
    query = parse_qs(parsed_result.query)

    # get the first value of a query parameter or None
    def _first_value(name: str) -> str | None:
        value = next(iter(query.get(name, [])), None)
        return value if isinstance(value, str) else None

    server = _first_value("url") or _first_value("server")
    school = _first_value("school")
    user = _first_value("user")
    key = _first_value("key")
    school_number = _first_value("schoolNumber")

    if server is None or school is None or user is None or key is None:
        raise ValueError("QR payload is incomplete")

    return QrData(
        server=_normalize_server_url(server),
        school=school,
        user=user,
        key=key,
        school_number=school_number,
    )
