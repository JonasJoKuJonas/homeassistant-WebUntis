"""Shared helpers for the WebUntis REST API used by the web and mobile apps.

The REST API authenticates with the JSESSIONID of the JSON-RPC session plus a
short-lived bearer token from /WebUntis/api/token/new.
"""

from __future__ import annotations

import base64
import json

import requests

TOKEN_ENDPOINT = "/WebUntis/api/token/new"
REQUEST_TIMEOUT = 20


class RestApiError(Exception):
    """Raised when a WebUntis REST request fails."""


def base_url(session) -> str:
    """Return the server URL without the JSON-RPC path."""
    return session.config["server"].replace("/WebUntis/jsonrpc.do", "")


def cookies(session) -> dict[str, str]:
    """Return the cookies the REST API expects for the current session."""
    # session.config is a webuntis FilterDict, which has no .get()
    if "jsessionid" not in session.config or not session.config["jsessionid"]:
        raise RestApiError("No JSESSIONID found, please log in first")
    jsessionid = session.config["jsessionid"]
    school = session.config["school"]
    schoolname = "_" + base64.b64encode(school.encode()).decode()
    return {"JSESSIONID": jsessionid, "schoolname": f'"{schoolname}"'}


def tenant_id(token: str) -> str | None:
    """Read the tenant id from the JWT payload; some servers require it as a header."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError):
        return None
    tenant = claims.get("tenant_id")
    return str(tenant) if tenant is not None else None


def get_token(session) -> str:
    """Request a bearer token for the REST API."""
    response = requests.get(
        base_url(session) + TOKEN_ENDPOINT,
        cookies=cookies(session),
        headers={"User-Agent": session.config["useragent"]},
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code != 200 or not response.text:
        raise RestApiError(f"Token request failed with status {response.status_code}")
    return response.text.strip().strip('"')


def auth_headers(session) -> dict[str, str]:
    """Return the request headers (bearer token, tenant) for REST calls."""
    token = get_token(session)
    headers = {
        "User-Agent": session.config["useragent"],
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    tenant = tenant_id(token)
    if tenant:
        headers["Tenant-Id"] = tenant
    return headers
