"""Messages ("Mitteilungen") via the WebUntis REST API.

The message list and the unread counter are read every update. The detail
endpoint (/messages/{id}) is only needed for attachments. It is unknown whether
it marks a message as read in WebUntis, so by default it is only called for
messages that are already read (or when a user opens an attachment link).
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

import requests
from homeassistant.util import dt as dt_util

from .rest_api import REQUEST_TIMEOUT, RestApiError, auth_headers, base_url, cookies

_LOGGER = logging.getLogger(__name__)

MESSAGES_ENDPOINT = "/WebUntis/api/rest/view/v1/messages"
MESSAGES_STATUS_ENDPOINT = "/WebUntis/api/rest/view/v1/messages/status"
# Takes the storage attachment id where other endpoints take a message id
ATTACHMENT_STORAGE_URL_ENDPOINT = (
    MESSAGES_ENDPOINT + "/{attachment_id}/attachmentstorageurl"
)
# Request headers of the storage URL response that must not be replayed
SKIPPED_STORAGE_HEADERS = ("host",)

# Status codes that mean the account has no access to messages
UNAVAILABLE_STATUS_CODES = (403, 404)


class MessagesUnavailableError(RestApiError):
    """Raised when messages are not available for this account."""


def _get_json(session, path: str, headers: dict[str, str]):
    response = requests.get(
        base_url(session) + path,
        cookies=cookies(session),
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    if response.status_code in UNAVAILABLE_STATUS_CODES:
        raise MessagesUnavailableError(
            f"Messages not available (status {response.status_code})"
        )
    if response.status_code != 200:
        raise RestApiError(
            f"Messages request failed with status {response.status_code}: "
            f"{response.text[:200]}"
        )
    try:
        return response.json()
    except ValueError as err:
        raise RestApiError("Invalid JSON in messages response") from err


def _parse_sent(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        # WebUntis returns school local time without an offset
        parsed = parsed.replace(tzinfo=dt_util.get_default_time_zone())
    return parsed


def parse_message(item: dict, requires_confirmation: bool = False) -> dict | None:
    """Convert one REST message item into the format used by the integration."""
    if not isinstance(item, dict) or item.get("id") is None:
        return None
    sender = item.get("sender") or {}
    if not isinstance(sender, dict):
        sender = {}
    sent = _parse_sent(item.get("sentDateTime"))
    return {
        "id": item["id"],
        "subject": item.get("subject") or "",
        "sender": sender.get("displayName") or "",
        "sent": sent.isoformat() if sent else None,
        "read": bool(item.get("isMessageRead")),
        "has_attachments": bool(item.get("hasAttachments")),
        "requires_confirmation": requires_confirmation,
        "text": item.get("contentPreview") or "",
    }


def parse_messages(data: dict) -> list[dict]:
    """Merge incoming and read confirmation messages, newest first."""
    messages: dict = {}
    if not isinstance(data, dict):
        return []
    for key, requires_confirmation in (
        ("incomingMessages", False),
        ("readConfirmationMessages", True),
    ):
        for item in data.get(key) or []:
            message = parse_message(item, requires_confirmation)
            if message is None:
                continue
            if message["id"] in messages:
                if requires_confirmation:
                    messages[message["id"]]["requires_confirmation"] = True
                continue
            messages[message["id"]] = message
    return sorted(
        messages.values(), key=lambda message: message["sent"] or "", reverse=True
    )


def fetch_messages(session) -> tuple[int, list[dict]] | None:
    """Return (unread count, messages), or None if messages are not available.

    Nothing is marked as read: only the list and the status endpoint are used.
    Attachments are added separately (see fetch_attachments).
    """
    headers = auth_headers(session)
    try:
        messages = parse_messages(_get_json(session, MESSAGES_ENDPOINT, headers))
    except MessagesUnavailableError as err:
        _LOGGER.debug("%s", err)
        return None

    unread = None
    try:
        status = _get_json(session, MESSAGES_STATUS_ENDPOINT, headers)
        if isinstance(status, dict) and isinstance(
            status.get("unreadMessagesCount"), int
        ):
            unread = status["unreadMessagesCount"]
    except (RestApiError, requests.RequestException) as err:
        _LOGGER.debug("Messages status not available: %s", err)
    if unread is None:
        unread = sum(1 for message in messages if not message["read"])
    return unread, messages


def truncate_text(text: str, length: int) -> str:
    """Shorten text to at most length characters, marking the cut with an ellipsis."""
    if len(text) <= length:
        return text
    return text[: length - 1].rstrip() + "…"


def shorten_message(message: dict, length: int) -> dict:
    """Return a copy of a message with the text shortened for state attributes."""
    return {**message, "text": truncate_text(message["text"], length)}


def _attribute_size(messages: list[dict]) -> int:
    return len(json.dumps(messages, ensure_ascii=False).encode())


def build_messages_attribute(
    messages: list[dict],
    max_messages: int,
    max_text_length: int,
    max_bytes: int,
    min_text_length: int | None = None,
) -> list[dict]:
    """Return the newest messages, shortened to fit into the attribute size limit.

    Over budget, the texts are first shortened to min_text_length (oldest message
    first), then the oldest messages are dropped. Attachment links are kept.
    """
    result = [
        shorten_message(message, max_text_length) for message in messages[:max_messages]
    ]
    if min_text_length is not None and min_text_length < max_text_length:
        for index in reversed(range(len(result))):
            if _attribute_size(result) <= max_bytes:
                break
            result[index] = shorten_message(result[index], min_text_length)
    while len(result) > 1 and _attribute_size(result) > max_bytes:
        result.pop()
    return result


def parse_attachments(detail) -> list[dict]:
    """Return the attachments of a message detail response.

    Storage attachments keep their WebUntis id (a UUID) and are downloaded via a
    presigned storage URL. Externally hosted attachments come with a direct
    download URL; they get their list index as id. Internal fields start with
    an underscore and are never exposed in state attributes.
    """
    attachments: list[dict] = []
    if not isinstance(detail, dict):
        return attachments
    for item in detail.get("storageAttachments") or []:
        if isinstance(item, dict) and item.get("id"):
            attachments.append(
                {
                    "id": str(item["id"]),
                    "name": item.get("name") or "attachment",
                    "_kind": "storage",
                }
            )
    for index, item in enumerate(detail.get("attachments") or []):
        if isinstance(item, dict) and item.get("downloadUrl"):
            attachments.append(
                {
                    "id": str(index),
                    "name": item.get("name") or "attachment",
                    "_kind": "external",
                    "_url": item["downloadUrl"],
                }
            )
    return attachments


def messages_without_attachment_list(
    messages: list[dict], loaded: dict, include_unread: bool
) -> list:
    """Return the ids of messages whose attachment list still has to be loaded.

    Unread messages are skipped unless include_unread is set, since opening a
    message may mark it as read in WebUntis.
    """
    return [
        message["id"]
        for message in messages
        if message["has_attachments"]
        and message["id"] not in loaded
        and (message["read"] or include_unread)
    ]


def fetch_attachments(session, message_ids) -> dict:
    """Return {message id: attachment list} for the given messages.

    Messages whose detail request fails are left out (retried next update).
    """
    result: dict = {}
    message_ids = list(message_ids)
    if not message_ids:
        return result
    headers = auth_headers(session)
    for message_id in message_ids:
        try:
            detail = _get_json(session, f"{MESSAGES_ENDPOINT}/{message_id}", headers)
        except (RestApiError, requests.RequestException) as err:
            _LOGGER.debug("Message %s details not available: %s", message_id, err)
            continue
        result[message_id] = parse_attachments(detail)
    return result


def _download(url: str, headers: dict[str, str]) -> bytes:
    if not url.startswith("https://"):
        raise RestApiError("Refusing non-HTTPS attachment URL")
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if response.status_code != 200:
        raise RestApiError(
            f"Attachment download failed with status {response.status_code}"
        )
    return response.content


def download_attachment(session, attachment: dict) -> bytes:
    """Download one attachment and return its content."""
    if attachment.get("_kind") == "external":
        return _download(attachment["_url"], {})
    storage = _get_json(
        session,
        ATTACHMENT_STORAGE_URL_ENDPOINT.format(attachment_id=attachment["id"]),
        auth_headers(session),
    )
    if not isinstance(storage, dict) or not storage.get("downloadUrl"):
        raise RestApiError("No download URL for attachment")
    headers = {
        header["key"]: header["value"]
        for header in storage.get("additionalHeaders") or []
        if isinstance(header, dict)
        and header.get("key")
        and header["key"].lower() not in SKIPPED_STORAGE_HEADERS
    }
    return _download(storage["downloadUrl"], headers)
