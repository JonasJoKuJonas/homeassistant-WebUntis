"""Helpers for WebUntis QR-code login."""

from __future__ import annotations

import logging
from dataclasses import dataclass
import time
from typing import Any
import aiohttp
from urllib.parse import parse_qs, urlparse
import pyotp
import webuntis
from voluptuous import Error

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "UntisMobileAndroid"
API_VERSION = "i3.2"


@dataclass(frozen=True)
class qrData:
    server: str
    school: str
    user: str
    key: str
    school_number: str | None = None


def _normalize_server_url(server: str) -> str:
    parsed = urlparse(server if "://" in server else f"https://{server}")
    host = (parsed.netloc or parsed.path.split("/", 1)[0]).strip()
    if not host:
        raise ValueError("QR payload does not contain a valid server")
    return host


def parse_qr_code(payload: str) -> qrData:
    """Parse the untis:// QR payload."""
    payload = payload.strip()

    if not payload.startswith("untis://"):
        if not payload.startswith("?"):
            raise ValueError("QR payload must start with untis://")
        payload = f"untis://setschool{payload}"

    parsed_result = urlparse(payload)
    query = parse_qs(parsed_result.query)

    # get the first value of a query parameter or None if not present
    _first_obj = lambda name: next(iter(query.get(name, [])), None)

    server = _first_obj("url") or _first_obj("server")
    school = _first_obj("school")
    user = _first_obj("user")
    key = _first_obj("key")
    school_number = _first_obj("schoolNumber")

    if not all([server, school, user, key]):
        raise ValueError("QR payload is incomplete")

    return qrData(
        server=_normalize_server_url(server), # type: ignore[arg-type]
        school=school,  # type: ignore[arg-type]
        user=user,  # type: ignore[arg-type]
        key=key,  # type: ignore[arg-type]
        school_number=school_number,
    )


def _extract_login_result(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields expected by webuntis.Session.login_result."""
    keys = ("personType", "personId", "klasseId")
    login_result = {k: data[k] for k in keys if k in data}

    result = data.get("result")
    if isinstance(result, dict):
        for key in keys:
            if key in result and key not in login_result:
                login_result[key] = result[key]

    return login_result


class WebUntisQrLogin:
    """Async QR login helper for the WebUntis JSON-RPC API."""

    def __init__(
        self,
        credentials: qrData,
        session: aiohttp.ClientSession,
    ) -> None:
        self._creds = credentials
        self._session = session

    @property
    def credentials(self) -> qrData:
        return self._creds

    def _endpoint(self, method: str) -> str:
        return (
            f"https://{self._creds.server}/WebUntis/jsonrpc_intern.do"
            f"?m={method}&school={self._creds.school}&v={API_VERSION}"
        )

    def _auth_block(self) -> dict[str, Any]:
        return {
            "user": self._creds.user,
            "otp": pyotp.TOTP(self._creds.key).now(),
            "clientTime": int(time.time() * 1000),
        }

    async def async_login(self) -> tuple[dict[str, Any], str]:
        """Return the WebUntis user data and JSESSIONID."""
        method = "getUserData2017"
        body = {
            "id": "ha-webuntis-qr",
            "method": method,
            "params": [{
                "auth": self._auth_block(),
                "deviceOs": "AND",
                "deviceOsVersion": "13",
            }],
            "jsonrpc": "2.0",
        }
        headers = {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT,
        }

        async with self._session.post(
            self._endpoint(method),
            json=body,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            resp.raise_for_status()
            data = await resp.json(content_type=None)

            if error := data.get("error"):
                msg = error.get("message", error) if isinstance(error, dict) else error
                raise Error(f"WebUntis error: {msg}")

            if not (jsessionid := resp.cookies.get("JSESSIONID")):
                raise Error("Could not find JSESSIONID in QR login response")

            result = data.get("result")
            return result if isinstance(result, dict) else {}, jsessionid.value

    def create_session(self, jsessionid: str) -> webuntis.Session:
        """Create a standard webuntis.Session bound to the QR cookie."""
        return webuntis.Session(
            server=self._creds.server,
            school=self._creds.school,
            username=self._creds.user,
            password="",
            jsessionid=jsessionid,
            useragent="home-assistant",
        )

    @staticmethod
    def login_result_from_user_data(user_data: dict[str, Any]) -> dict[str, Any]:
        """Convert QR user data into a standard session login_result payload."""
        return _extract_login_result(user_data)