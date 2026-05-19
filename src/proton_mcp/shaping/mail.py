"""Pure shaping helpers: RFC822 → compact dicts, handle codec, folder
metadata extraction."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from dataclasses import dataclass
from email.message import Message
from typing import Any

# IMAP SPECIAL-USE flags → friendly kind. See RFC 6154.
_SPECIAL_USE_FLAGS: dict[bytes, str] = {
    b"\\All": "all",
    b"\\Archive": "archive",
    b"\\Drafts": "drafts",
    b"\\Flagged": "flagged",
    b"\\Junk": "junk",
    b"\\Sent": "sent",
    b"\\Trash": "trash",
    b"\\Important": "important",
}


@dataclass(frozen=True)
class MessageHandle:
    """Composite IMAP identifier: folder:uidvalidity:uid."""

    folder: str
    uidvalidity: int
    uid: int


def encode_handle(handle: MessageHandle) -> str:
    return f"{handle.folder}:{handle.uidvalidity}:{handle.uid}"


def parse_handle(encoded: str) -> MessageHandle:
    """Parse a 'folder:uidvalidity:uid' string into a MessageHandle.

    Folder names can contain ':' in theory but Proton Bridge doesn't use
    them in practice; we split from the right so folder names with one
    colon still parse. Two or more colons in the folder would break this;
    callers should treat that as malformed input.
    """
    parts = encoded.rsplit(":", 2)
    if len(parts) != 3 or not parts[0]:
        raise ValueError(f"malformed message handle: {encoded!r}")
    folder, uv_str, uid_str = parts
    try:
        uidvalidity = int(uv_str)
        uid = int(uid_str)
    except ValueError as e:
        raise ValueError(f"malformed message handle: {encoded!r}") from e
    return MessageHandle(folder=folder, uidvalidity=uidvalidity, uid=uid)


def shape_folder(
    *,
    flags: Iterable[bytes],
    delimiter: bytes,
    name: bytes,
    message_count: int,
    unseen_count: int,
) -> dict[str, Any]:
    """Shape an IMAP LIST + STATUS result into a folder dict."""
    flag_set = set(flags)
    kind: str | None = None
    for flag, mapped in _SPECIAL_USE_FLAGS.items():
        if flag in flag_set:
            kind = mapped
            break
    name_str = name.decode("utf-8", errors="replace")
    return {
        "name": name_str,
        "path": name_str,
        "is_special": kind is not None,
        "special_kind": kind,
        "message_count": message_count,
        "unseen_count": unseen_count,
    }


def _flags_to_strings(flags: Iterable[bytes]) -> list[str]:
    return [f.decode("ascii", errors="replace") for f in flags]


def _snippet(msg: Message, *, max_chars: int = 200) -> str:
    body = _extract_text_body(msg)
    cleaned = re.sub(r"\s+", " ", body).strip()
    return cleaned[:max_chars]


def shape_message_summary(
    msg: Message,
    *,
    handle: str,
    folder: str,
    flags: Iterable[bytes],
) -> dict[str, Any]:
    """Compact dict for search results."""
    return {
        "handle": handle,
        "message_id": msg.get("Message-ID", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "folder": folder,
        "flags": _flags_to_strings(flags),
        "snippet": _snippet(msg),
    }


def shape_message_full(
    msg: Message,
    *,
    handle: str,
    folder: str,
    flags: Iterable[bytes],
) -> dict[str, Any]:
    """Summary + body_text + attachments metadata."""
    summary = shape_message_summary(
        msg, handle=handle, folder=folder, flags=flags
    )
    return {
        **summary,
        "body_text": _extract_text_body(msg),
        "attachments": shape_attachment_list(msg),
    }


def shape_attachment_list(msg: Message) -> list[dict[str, Any]]:
    """List attachment metadata. attachment_id is a stable hash of the
    filename + content-id + position so callers can re-fetch via
    mail_get_attachment without us needing an actual ID from the IMAP
    server."""
    out: list[dict[str, Any]] = []
    index = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        cid = part.get("Content-ID", "")
        index += 1
        attachment_id = hashlib.sha256(
            f"{index}:{filename}:{cid}".encode()
        ).hexdigest()[:16]
        out.append(
            {
                "attachment_id": attachment_id,
                "filename": filename,
                "mime": part.get_content_type(),
                "size": len(payload),
                "_part_index": index,
            }
        )
    return out


def _extract_text_body(msg: Message) -> str:
    """Prefer text/plain; fall back to stripped text/html."""
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if not isinstance(payload, bytes):
                continue
            charset = part.get_content_charset() or "utf-8"
            html = payload.decode(charset, errors="replace")
            no_tags = re.sub(r"<[^>]+>", "", html)
            return re.sub(r"\s+", " ", no_tags).strip()
    return ""


def truncate_body(body: str, *, cap: int) -> str:
    raw = body.encode("utf-8")
    if len(raw) <= cap:
        return body
    cut = raw[:cap].decode("utf-8", errors="replace")
    return f"{cut}\n\n[...truncated: {len(raw)} bytes total, showing first {cap}]"
