"""MCP tool implementations for Proton Mail via Bridge."""

from __future__ import annotations

import base64
import datetime as dt
from dataclasses import asdict
from email import message_from_bytes
from email.message import Message
from typing import Any

from proton_mcp import config
from proton_mcp.accounts import AccountStore
from proton_mcp.bridge import BridgeSession
from proton_mcp.exceptions import AttachmentTooLarge, MessageHandleStale
from proton_mcp.shaping.mail import (
    MessageHandle,
    encode_handle,
    parse_handle,
    shape_attachment_list,
    shape_folder,
    shape_message_full,
    shape_message_summary,
    truncate_body,
)

_store = AccountStore()


def _session(account: str) -> BridgeSession:
    return BridgeSession(_store.load(account))


def list_accounts() -> list[dict[str, str]]:
    return [asdict(a) for a in _store.list()]


def mail_list_folders(account: str) -> list[dict[str, Any]]:
    session = _session(account)
    imap = session.imap()
    try:
        listed = imap.list_folders()
        out: list[dict[str, Any]] = []
        for flags, delimiter, name in listed:
            name_bytes = name.encode("utf-8") if isinstance(name, str) else name
            status = imap.folder_status(name, [b"MESSAGES", b"UNSEEN"])
            out.append(
                shape_folder(
                    flags=flags,
                    delimiter=delimiter,
                    name=name_bytes,
                    message_count=int(status.get(b"MESSAGES", 0)),
                    unseen_count=int(status.get(b"UNSEEN", 0)),
                )
            )
        return out
    finally:
        try:
            imap.logout()
        except Exception:
            pass


_DATE_FIELDS = {"since", "before"}
_TEXT_FIELDS = {
    "from": "FROM",
    "to": "TO",
    "cc": "CC",
    "subject": "SUBJECT",
    "text": "TEXT",
}
_FLAG_FIELDS = {
    "seen": ("SEEN", "UNSEEN"),
    "flagged": ("FLAGGED", "UNFLAGGED"),
    "answered": ("ANSWERED", "UNANSWERED"),
}


def _build_search_criteria(query: dict[str, Any]) -> list[Any]:
    """Translate {from, subject, since, seen, ...} into imapclient SEARCH args."""
    if not query:
        return ["ALL"]
    criteria: list[Any] = []
    for k, v in query.items():
        if k in _TEXT_FIELDS and v:
            criteria.extend([_TEXT_FIELDS[k], str(v)])
        elif k in _DATE_FIELDS and v:
            parsed = dt.date.fromisoformat(str(v))
            criteria.extend([k.upper(), parsed.strftime("%d-%b-%Y")])
        elif k in _FLAG_FIELDS:
            on, off = _FLAG_FIELDS[k]
            criteria.append(on if v else off)
    if not criteria:
        return ["ALL"]
    return criteria


def mail_search(
    account: str,
    query: dict[str, Any],
    folder: str = "INBOX",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    session = _session(account)
    imap = session.imap()
    try:
        select_info = imap.select_folder(folder, readonly=True)
        uidvalidity = int(select_info[b"UIDVALIDITY"])
        criteria = _build_search_criteria(query)
        uids = imap.search(criteria)
        uids_sorted = sorted(uids, reverse=True)[:max_results]
        if not uids_sorted:
            return []
        fetched = imap.fetch(uids_sorted, [b"FLAGS", b"RFC822.HEADER"])

        out: list[dict[str, Any]] = []
        for uid in uids_sorted:
            data = fetched.get(uid)
            if data is None:
                continue
            header_bytes = data.get(b"RFC822.HEADER", b"")
            msg = message_from_bytes(header_bytes)
            handle = encode_handle(
                MessageHandle(folder=folder, uidvalidity=uidvalidity, uid=uid)
            )
            out.append(
                shape_message_summary(
                    msg,
                    handle=handle,
                    folder=folder,
                    flags=data.get(b"FLAGS", ()),
                )
            )
        return out
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _fetch_full_message(imap: Any, handle_str: str) -> tuple[Message, dict[bytes, Any]]:
    """Open the folder, validate UIDVALIDITY, return (parsed email, fetch_data)."""
    handle = parse_handle(handle_str)
    select_info = imap.select_folder(handle.folder, readonly=True)
    if int(select_info[b"UIDVALIDITY"]) != handle.uidvalidity:
        raise MessageHandleStale(handle_str)
    fetched = imap.fetch([handle.uid], [b"FLAGS", b"RFC822"])
    data = fetched.get(handle.uid)
    if data is None:
        raise MessageHandleStale(handle_str)
    msg = message_from_bytes(data[b"RFC822"])
    return msg, data


def mail_get_message(account: str, handle: str) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        msg, data = _fetch_full_message(imap, handle)
        h = parse_handle(handle)
        shaped = shape_message_full(
            msg, handle=handle, folder=h.folder, flags=data.get(b"FLAGS", ())
        )
        shaped["body_text"] = truncate_body(
            shaped["body_text"], cap=config.MAX_MAIL_BODY_BYTES
        )
        for att in shaped["attachments"]:
            att.pop("_part_index", None)
        return shaped
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def mail_get_attachment(
    account: str, handle: str, attachment_id: str
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        msg, _data = _fetch_full_message(imap, handle)
        atts = shape_attachment_list(msg)
        match = next(
            (a for a in atts if a["attachment_id"] == attachment_id), None
        )
        if match is None:
            raise ValueError(
                f"attachment {attachment_id!r} not found on message {handle!r}"
            )
        if match["size"] > config.MAX_ATTACHMENT_BYTES:
            raise AttachmentTooLarge(
                size=match["size"], cap=config.MAX_ATTACHMENT_BYTES
            )
        target_index = match["_part_index"]
        index = 0
        payload = b""
        for part in msg.walk():
            if part.is_multipart():
                continue
            if not part.get_filename():
                continue
            index += 1
            if index == target_index:
                decoded = part.get_payload(decode=True)
                if isinstance(decoded, bytes):
                    payload = decoded
                break
        return {
            "filename": match["filename"],
            "mime": match["mime"],
            "size": match["size"],
            "content_b64": base64.b64encode(payload).decode("ascii"),
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass
