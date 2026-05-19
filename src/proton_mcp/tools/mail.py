"""MCP tool implementations for Proton Mail via Bridge."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from proton_mcp.accounts import AccountStore
from proton_mcp.bridge import BridgeSession
from proton_mcp.shaping.mail import shape_folder

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
