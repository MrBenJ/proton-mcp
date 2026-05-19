"""MCP tool implementations for Proton Mail via Bridge."""

from __future__ import annotations

import base64
import datetime as dt
from dataclasses import asdict
from email import message_from_bytes
from email.message import EmailMessage, Message
from email.utils import make_msgid
from typing import Any

from proton_mcp import config
from proton_mcp.accounts import AccountStore
from proton_mcp.bridge import BridgeSession
from proton_mcp.exceptions import (
    AttachmentTooLarge,
    MessageHandleStale,
    OutboundTooLarge,
)
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


def _build_outbound(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    bcc: str | None,
    html: bool,
    in_reply_to: str | None,
    attachments: list[dict[str, Any]] | None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    if html:
        msg.set_content("This message contains HTML — please use an HTML client.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    for att in attachments or []:
        raw = base64.b64decode(att["content_b64"])
        maintype, _, subtype = att["mime"].partition("/")
        msg.add_attachment(
            raw,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att["filename"],
        )

    total = len(bytes(msg))
    if total > config.MAX_OUTBOUND_BYTES:
        raise OutboundTooLarge(size=total, cap=config.MAX_OUTBOUND_BYTES)
    return msg


def mail_send(
    account: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    rec = _store.load(account)
    msg = _build_outbound(
        sender=rec.email,
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        html=html,
        in_reply_to=in_reply_to,
        attachments=attachments,
    )
    smtp = BridgeSession(rec).smtp()
    try:
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    return {"message_id": str(msg["Message-ID"])}


def _find_special_folder(imap: Any, kind: str) -> str:
    """Resolve a SPECIAL-USE folder (\\Drafts, \\Trash, ...) to its name."""
    flag = f"\\{kind.capitalize()}".encode()
    for flags, _delim, name in imap.list_folders():
        if flag in flags:
            return str(name) if isinstance(name, str) else name.decode("utf-8")
    raise ValueError(f"no folder marked as {kind!r} on this account")


def mail_create_draft(
    account: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    rec = _store.load(account)
    msg = _build_outbound(
        sender=rec.email,
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        html=html,
        in_reply_to=in_reply_to,
        attachments=attachments,
    )
    session = BridgeSession(rec)
    imap = session.imap()
    try:
        drafts = _find_special_folder(imap, "drafts")
        imap.append(drafts, bytes(msg), [b"\\Draft"], None)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return {"message_id": str(msg["Message-ID"])}


def _open_for_write(imap: Any, handle_str: str) -> int:
    """select_folder (writeable) and validate UIDVALIDITY; return uid."""
    handle = parse_handle(handle_str)
    select_info = imap.select_folder(handle.folder, readonly=False)
    if int(select_info[b"UIDVALIDITY"]) != handle.uidvalidity:
        raise MessageHandleStale(handle_str)
    return handle.uid


def mail_modify_flags(
    account: str,
    handle: str,
    add_flags: list[str] | None = None,
    remove_flags: list[str] | None = None,
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        if add_flags:
            imap.add_flags([uid], [f.encode("ascii") for f in add_flags])
        if remove_flags:
            imap.remove_flags([uid], [f.encode("ascii") for f in remove_flags])
        current = imap.get_flags([uid]).get(uid, ())
        return {
            "handle": handle,
            "flags": [f.decode("ascii", errors="replace") for f in current],
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _move_uid(imap: Any, uid: int, dest_folder: str) -> None:
    """IMAP MOVE if advertised, else COPY + \\Deleted + EXPUNGE."""
    if imap.has_capability("MOVE"):
        imap.move([uid], dest_folder)
    else:
        imap.copy([uid], dest_folder)
        imap.add_flags([uid], [b"\\Deleted"])
        imap.expunge()


def mail_move_message(
    account: str, handle: str, dest_folder: str
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        _move_uid(imap, uid, dest_folder)
        return {"handle": handle, "moved_to": dest_folder}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def mail_trash(account: str, handle: str) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        trash = _find_special_folder(imap, "trash")
        _move_uid(imap, uid, trash)
        return {"handle": handle, "moved_to": trash}
    finally:
        try:
            imap.logout()
        except Exception:
            pass
