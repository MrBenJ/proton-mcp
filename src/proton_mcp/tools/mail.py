"""MCP tool implementations for Proton Mail via Bridge."""

from __future__ import annotations

import datetime as dt
from dataclasses import asdict
from email import message_from_bytes
from typing import Any

from proton_mcp.accounts import AccountStore
from proton_mcp.bridge import BridgeSession
from proton_mcp.shaping.mail import (
    MessageHandle,
    encode_handle,
    shape_folder,
    shape_message_summary,
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
