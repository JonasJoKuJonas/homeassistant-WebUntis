"""Helpers for WebUntis QR-code login."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

import time
from typing import Any

import aiohttp
import pyotp
from webuntis import errors


@dataclass(frozen=True)
class QrData:
    server: str
    school: str
    user: str
    key: str
    school_number: str | None = None


qrData = QrData

QR_USER_AGENT = "UntisMobileAndroid"
QR_API_VERSION = "i3.2"


def extract_login_result(data: dict[str, Any]) -> dict[str, Any]:
    """Extract fields expected by webuntis.Session.login_result from QR user_data."""
    login_result = {}

    type_map = {
        "KLASSE": 1,
        "TEACHER": 2,
        "SUBJECT": 3,
        "ROOM": 4,
        "STUDENT": 5,
    }

    user_data = data.get("userData", {}) if isinstance(data, dict) else {}

    if "elemId" in user_data:
        login_result["personId"] = user_data["elemId"]

    if "elemType" in user_data:
        elem_type = user_data["elemType"]
        if isinstance(elem_type, str):
            login_result["personType"] = type_map.get(elem_type.upper(), 5)
        else:
            login_result["personType"] = elem_type

    if user_data.get("klassenIds"):
        login_result["klasseId"] = user_data["klassenIds"][0]

    # Fallback for default keys
    for key in ("personType", "personId", "klasseId"):
        if key in data and key not in login_result:
            login_result[key] = data[key]

    return login_result


async def async_qr_login(
    credentials: QrData,
    client_session: aiohttp.ClientSession,
) -> tuple[dict[str, Any], str]:
    """Authenticate via QR credentials and return user payload and JSESSIONID."""
    method = "getUserData2017"

    # 1. TOTP generieren
    totp = pyotp.TOTP(credentials.key)
    otp_value = totp.now()

    body = {
        "id": "ha-webuntis-qr",
        "method": method,
        "params": [
            {
                "auth": {
                    "user": credentials.user,
                    "otp": int(otp_value) if otp_value.isdigit() else otp_value,
                    "clientTime": int(time.time() * 1000),
                },
                "deviceOs": "AND",
                "deviceOsVersion": "13",
            }
        ],
        "jsonrpc": "2.0",
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": QR_USER_AGENT,
    }

    url = _qr_endpoint(credentials, method)

    async with client_session.post(
        url,
        json=body,
        headers=headers,
        timeout=aiohttp.ClientTimeout(total=20),
    ) as response:
        response.raise_for_status()
        data = await response.json(content_type=None)

        error = data.get("error")
        if error:
            message = error.get("message", error) if isinstance(error, dict) else error
            code = error.get("code", "") if isinstance(error, dict) else ""
            raise errors.NotLoggedInError(f"WebUntis RPC Error ({code}): {message}")

        result = data.get("result")
        user_data = result if isinstance(result, dict) else {}

        jsessionid = None

        if "JSESSIONID" in response.cookies:
            jsessionid = response.cookies["JSESSIONID"].value

        if not jsessionid and client_session.cookie_jar:
            for cookie in client_session.cookie_jar:
                if cookie.key == "JSESSIONID":
                    jsessionid = cookie.value
                    break

        if not jsessionid:
            set_cookie_headers = response.headers.getall("Set-Cookie", [])
            for header in set_cookie_headers:
                if "JSESSIONID=" in header:
                    jsessionid = header.split("JSESSIONID=")[1].split(";")[0].strip()
                    break

        if not jsessionid and isinstance(user_data, dict):
            jsessionid = user_data.get("sessionId")

        if not jsessionid:
            raise errors.NotLoggedInError(
                f"WebUntis lehnte Session ab oder sendete keine JSESSIONID. Response: {data}"
            )

        return user_data, jsessionid


def _normalize_server_url(server: str) -> str:
    parsed = urlparse(server if "://" in server else f"https://{server}")
    host = (parsed.netloc or parsed.path.split("/", 1)[0]).strip()
    if not host:
        raise ValueError("QR payload does not contain a valid server")
    return host


def _qr_endpoint(credentials: QrData, method: str) -> str:
    """Build the API endpoint URL for QR login."""
    return (
        f"https://{credentials.server}/WebUntis/jsonrpc_intern.do"
        f"?m={method}&school={credentials.school}&v={QR_API_VERSION}"
    )


def _qr_auth_block(credentials: QrData) -> dict[str, Any]:
    """Generate auth block with TOTP for QR login."""
    return {
        "user": credentials.user,
        "otp": pyotp.TOTP(credentials.key).now(),
        "clientTime": int(time.time() * 1000),
    }


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
