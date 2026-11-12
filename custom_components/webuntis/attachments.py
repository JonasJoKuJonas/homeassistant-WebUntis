"""Download links for the attachments of WebUntis messages ("Mitteilungen").

Attachments are served by a Home Assistant view. The sensor attribute contains
relative links with an integration token (HMAC over entry, message, attachment
and expiry). The token is checked instead of HA's authSig because apps add
query parameters (e.g. the companion app adds external_auth=1), which an authSig
does not allow. Requests of logged-in users are accepted without a token.
Nothing is stored in /local, www or the media folder.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
import mimetypes
import secrets
from datetime import datetime, timedelta
from html import escape
from http import HTTPStatus
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote

from aiohttp import web
from homeassistant.components.http import KEY_AUTHENTICATED, HomeAssistantView
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    MESSAGES_ATTACHMENT_URL_EXPIRY,
    MESSAGES_ATTACHMENT_URL_RENEW,
    MESSAGES_ATTACHMENT_VIEW_URL,
    MESSAGES_ATTACHMENTS_PLACEHOLDER,
)
from .utils.messages import download_attachment, fetch_attachments

if TYPE_CHECKING:
    from . import WebUntis

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY = "webuntis.attachment_links"
STORAGE_VERSION = 1
DATA_LINK_SECRET = "attachment_link_secret"
DATA_LINK_SECRET_LOCK = "attachment_link_secret_lock"
TOKEN_PARAM = "token"


async def async_load_link_secret(hass: HomeAssistant) -> bytes:
    """Load (or create once) the secret for attachment link tokens.

    It is kept in .storage, so links sent earlier keep working after a restart.
    """
    domain_data = hass.data.setdefault(DOMAIN, {})
    if DATA_LINK_SECRET in domain_data:
        return domain_data[DATA_LINK_SECRET]
    lock = domain_data.setdefault(DATA_LINK_SECRET_LOCK, asyncio.Lock())
    async with lock:
        if DATA_LINK_SECRET not in domain_data:
            store: Store = Store(hass, STORAGE_VERSION, STORAGE_KEY, private=True)
            data = await store.async_load()
            secret = None
            if isinstance(data, dict) and isinstance(data.get("secret"), str):
                try:
                    secret = base64.urlsafe_b64decode(data["secret"])
                except ValueError:
                    secret = None
            if not secret or len(secret) < 32:
                secret = secrets.token_bytes(32)
                await store.async_save(
                    {"secret": base64.urlsafe_b64encode(secret).decode()}
                )
            domain_data[DATA_LINK_SECRET] = secret
    return domain_data[DATA_LINK_SECRET]


def _signature(secret: bytes, entry_id, message_id, attachment_id, exp: int) -> str:
    message = f"{entry_id}/{message_id}/{attachment_id or 'list'}/{exp}"
    digest = hmac.new(secret, message.encode(), hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def make_token(secret: bytes, entry_id, message_id, attachment_id, exp: int) -> str:
    """Return a link token "<exp>.<signature>"."""
    return f"{exp}.{_signature(secret, entry_id, message_id, attachment_id, exp)}"


def verify_token(
    secret: bytes, token: str | None, entry_id, message_id, attachment_id, now: datetime
) -> bool:
    """Return True if the token is valid for this link and not expired."""
    if not token or "." not in token:
        return False
    exp_text, signature = token.split(".", 1)
    try:
        exp = int(exp_text)
    except ValueError:
        return False
    if exp <= now.timestamp():
        return False
    expected = _signature(secret, entry_id, message_id, attachment_id, exp)
    return hmac.compare_digest(expected.encode(), signature.encode())


def attachments_path(entry_id: str, message_id) -> str:
    """Return the view path for all attachments of a message."""
    return MESSAGES_ATTACHMENT_VIEW_URL.format(
        entry_id=entry_id, message_id=quote(str(message_id), safe="")
    )


def attachment_path(entry_id: str, message_id, attachment_id: str) -> str:
    """Return the view path for one attachment."""
    return attachments_path(entry_id, message_id) + "/" + quote(attachment_id, safe="")


@callback
def async_link(
    secret: bytes,
    cache: dict[str, tuple[str, datetime]],
    entry_id: str,
    message_id,
    attachment_id: str | None = None,
) -> str:
    """Return the relative link with token, renewed only when it expires within a day.

    Keeping the link stable avoids a new sensor state (and recorder row) every
    update.
    """
    if attachment_id is None:
        path = attachments_path(entry_id, message_id)
    else:
        path = attachment_path(entry_id, message_id, attachment_id)
    now = dt_util.utcnow()
    cached = cache.get(path)
    if cached and cached[1] - now > timedelta(seconds=MESSAGES_ATTACHMENT_URL_RENEW):
        return cached[0]
    expires = now + timedelta(seconds=MESSAGES_ATTACHMENT_URL_EXPIRY)
    exp = int(expires.timestamp())
    token = make_token(secret, entry_id, str(message_id), attachment_id, exp)
    url = f"{path}?{TOKEN_PARAM}={token}"
    cache[path] = (url, expires)
    return url


def _server_link(server: WebUntis, message_id, attachment_id: str | None) -> str:
    return async_link(
        server.hass.data[DOMAIN][DATA_LINK_SECRET],
        server.attachment_urls,
        server.entry_id,
        message_id,
        attachment_id,
    )


@callback
def async_add_attachment_links(server: WebUntis) -> None:
    """Add the "attachments" list ({name, url}) to every known message."""
    cache = server.attachment_urls
    keep: dict[str, tuple[str, datetime]] = {}

    def link(message_id, attachment_id: str | None = None) -> str:
        url = _server_link(server, message_id, attachment_id)
        keep[url.split("?", 1)[0]] = cache[url.split("?", 1)[0]]
        return url

    for message in server.messages:
        attachments = server.message_attachments.get(message["id"])
        if attachments is not None:
            message["attachments"] = [
                {
                    "name": attachment["name"],
                    "url": link(message["id"], attachment["id"]),
                }
                for attachment in attachments
            ]
        elif message["has_attachments"]:
            # Not loaded yet (unread): the link loads them when it is opened
            message["attachments"] = [
                {"name": MESSAGES_ATTACHMENTS_PLACEHOLDER, "url": link(message["id"])}
            ]
        else:
            message["attachments"] = []

    cache.clear()
    cache.update(keep)


def _file_response(name: str, content: bytes) -> web.Response:
    content_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return web.Response(
        body=content,
        content_type=content_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{quote(name, safe='')}",
            "Cache-Control": "private, no-store",
        },
    )


def _list_response(
    server: WebUntis, message_id, attachments: list[dict]
) -> web.Response:
    items = "".join(
        '<li><a href="{}">{}</a></li>'.format(
            escape(_server_link(server, message_id, attachment["id"])),
            escape(attachment["name"]),
        )
        for attachment in attachments
    )
    body = (
        '<!doctype html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<style>body{font-family:-apple-system,system-ui,sans-serif;font-size:18px;"
        "line-height:1.5;margin:16px}li{margin:12px 0}a{word-break:break-word}</style>"
        f"<title>WebUntis</title></head><body><ul>{items}</ul></body></html>"
    )
    return web.Response(
        text=body,
        content_type="text/html",
        headers={"Cache-Control": "private, no-store"},
    )


class WebUntisAttachmentView(HomeAssistantView):
    """Serve attachments of the messages known to a WebUntis config entry."""

    url = MESSAGES_ATTACHMENT_VIEW_URL
    extra_urls: ClassVar[list[str]] = [
        MESSAGES_ATTACHMENT_VIEW_URL + "/{attachment_id}"
    ]
    name = "api:webuntis:message_attachments"
    # Checked in get(): a logged-in user or a valid link token
    requires_auth = False

    async def get(
        self,
        request: web.Request,
        entry_id: str,
        message_id: str,
        attachment_id: str | None = None,
    ) -> web.Response:
        """Return one attachment, or all attachments of a message."""
        hass: HomeAssistant = request.app["hass"]
        secret = hass.data.get(DOMAIN, {}).get(DATA_LINK_SECRET)
        # Other query parameters (e.g. external_auth=1) are ignored
        if not request.get(KEY_AUTHENTICATED) and not (
            secret
            and verify_token(
                secret,
                request.query.get(TOKEN_PARAM),
                entry_id,
                message_id,
                attachment_id,
                dt_util.utcnow(),
            )
        ):
            return web.Response(status=HTTPStatus.UNAUTHORIZED, text="Unauthorized")

        entry = hass.config_entries.async_get_entry(entry_id)
        server: WebUntis | None = None
        if entry is not None and entry.domain == DOMAIN:
            server = hass.data.get(DOMAIN, {}).get(entry.unique_id)
        if server is None or not server.message_attachments_enabled:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Not found")

        # Only messages currently known for this entry: no generic proxy
        message = next((m for m in server.messages if str(m["id"]) == message_id), None)
        if message is None or not message["has_attachments"]:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown message")
        message_key = message["id"]

        cached = server.message_attachments.get(message_key)
        if attachment_id is not None and (
            cached is None or not any(a["id"] == attachment_id for a in cached)
        ):
            return web.Response(status=HTTPStatus.NOT_FOUND, text="Unknown attachment")

        try:
            attachments, content = await server.async_with_session(
                lambda: self._load(server, message_key, cached, attachment_id)
            )
        except Exception as err:
            _LOGGER.warning(
                "Loading attachment %s of message %s failed: %s",
                attachment_id or "list",
                message_key,
                err,
            )
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text="WebUntis error")

        if attachments is None:
            return web.Response(status=HTTPStatus.BAD_GATEWAY, text="WebUntis error")
        server.message_attachments[message_key] = attachments
        if content is not None:
            return _file_response(content[0], content[1])
        if not attachments:
            return web.Response(status=HTTPStatus.NOT_FOUND, text="No attachments")
        return _list_response(server, message_key, attachments)

    @staticmethod
    def _load(server: WebUntis, message_id, cached, attachment_id):
        """Run in the executor: (attachment list, (name, bytes) or None)."""
        attachments = cached
        if attachments is None:
            attachments = fetch_attachments(server.session, [message_id]).get(
                message_id
            )
            if attachments is None:
                return None, None
        if attachment_id is not None:
            attachment = next(a for a in attachments if a["id"] == attachment_id)
        elif len(attachments) == 1:
            attachment = attachments[0]
        else:
            return attachments, None
        return attachments, (
            attachment["name"],
            download_attachment(server.session, attachment),
        )
