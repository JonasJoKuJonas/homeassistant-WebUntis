"""Helpers for WebUntis QR-code login."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import aiohttp
import pyotp
import webuntis
from voluptuous import Error

_LOGGER = logging.getLogger(__name__)

USER_AGENT = "UntisMobileAndroid"
API_VERSION = "i3.2"


@dataclass(frozen=True)
class WebUntisCredentials:
    """Credentials extracted from the QR payload."""

    server: str
    school: str
    user: str
    key: str
    school_number: str | None = None


def _normalize_server(server: str) -> str:
    """Return a host name that can be used by webuntis.Session."""
    parsed = urlparse(server if "://" in server else f"https://{server}")
    host = parsed.netloc or parsed.path.split("/", 1)[0]
    host = host.strip()
    if not host:
        raise ValueError("QR payload does not contain a valid server")
    return host


def parse_qr_payload(payload: str) -> WebUntisCredentials:
    """Parse the untis:// QR payload."""
    payload = payload.strip()

    if not payload.startswith("untis://"):
        if payload.startswith("?"):
            payload = "untis://setschool" + payload
        else:
            raise ValueError("QR payload must start with untis://")

    parsed = urlparse(payload)
    query = parse_qs(parsed.query)

    def _first(name: str) -> str | None:
        values = query.get(name)
        return values[0] if values else None

    server = _first("url") or _first("server")
    school = _first("school")
    user = _first("user")
    key = _first("key")
    school_number = _first("schoolNumber")

    if not all([server, school, user, key]):
        raise ValueError("QR payload is incomplete")

    return WebUntisCredentials(
        server=_normalize_server(server),
        school=school,
        user=user,
        key=key,
        school_number=school_number,
    )


def _extract_login_result(data: dict[str, Any]) -> dict[str, Any]:
    """Extract the fields expected by webuntis.Session.login_result."""
    login_result: dict[str, Any] = {}

    for key in ("personType", "personId", "klasseId"):
        if key in data:
            login_result[key] = data[key]

    result = data.get("result")
    if isinstance(result, dict):
        for key in ("personType", "personId", "klasseId"):
            if key in result and key not in login_result:
                login_result[key] = result[key]

    return login_result


class WebUntisQrClient:
    """Asynchronous QR login helper for the WebUntis JSON-RPC API."""

    def __init__(
        self,
        credentials: WebUntisCredentials,
        session: aiohttp.ClientSession,
    ) -> None:
        self._creds = credentials
        self._session = session

    @property
    def credentials(self) -> WebUntisCredentials:
        return self._creds

    def _endpoint(self, method: str) -> str:
        return (
            f"https://{self._creds.server}/WebUntis/jsonrpc_intern.do"
            f"?m={method}&school={self._creds.school}&v={API_VERSION}"
        )

    def _auth_block(self) -> dict[str, Any]:
        totp = pyotp.TOTP(self._creds.key)
        return {
            "user": self._creds.user,
            "otp": totp.now(),
            "clientTime": int(time.time() * 1000),
        }

    async def async_login(self) -> tuple[dict[str, Any], str]:
        """Return the WebUntis user data and JSESSIONID."""
        method = "getUserData2017"
        body = {
            "id": "ha-webuntis-qr",
            "method": method,
            "params": [
                {
                    "auth": self._auth_block(),
                    "deviceOs": "AND",
                    "deviceOsVersion": "13",
                }
            ],
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

            if data.get("error"):
                raise Error(
                    f"WebUntis error: {data['error'].get('message', data['error'])}"
                )

            jsessionid = resp.cookies.get("JSESSIONID")
            if not jsessionid:
                raise Error("Could not find JSESSIONID in QR login response")

            result = data.get("result", {})
            if not isinstance(result, dict):
                result = {}

            return result, jsessionid.value

    def create_session(self, jsessionid: str) -> webuntis.Session:
        """Create a standard webuntis.Session bound to the QR cookie."""
        session = webuntis.Session(
            server=self._creds.server,
            school=self._creds.school,
            username=self._creds.user,
            password="",
            jsessionid=jsessionid,
            useragent="home-assistant",
        )
        return session

    @staticmethod
    def login_result_from_user_data(user_data: dict[str, Any]) -> dict[str, Any]:
        """Convert QR user data into a standard session login_result payload."""
        return _extract_login_result(user_data)
