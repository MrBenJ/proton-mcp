"""proton-mcp-auth: manage local Bridge credentials for the MCP server."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from proton_mcp import config
from proton_mcp.accounts import AccountRecord, AccountStore
from proton_mcp.bridge import BridgeSession, probe_fingerprint
from proton_mcp.exceptions import (
    AccountNotConfigured,
    ProtonMcpError,
)


def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _prompt_int(prompt: str, default: int) -> int:
    raw = _prompt(prompt, str(default))
    return int(raw)


def _validate(record: AccountRecord) -> None:
    """Open and close an IMAP session to check credentials and fingerprint."""
    session = BridgeSession(record)
    imap = session.imap()
    try:
        imap.logout()
    except Exception:
        pass


def _cmd_add(label: str) -> int:
    email = _prompt("Proton email")
    if not email:
        print("error: email is required", file=sys.stderr)
        return 1
    bridge_password = getpass.getpass("Bridge app password (hidden): ")
    if not bridge_password:
        print("error: bridge password is required", file=sys.stderr)
        return 1
    imap_host = _prompt("Bridge IMAP host", config.DEFAULT_IMAP_HOST)
    imap_port = _prompt_int("Bridge IMAP port", config.DEFAULT_IMAP_PORT)
    smtp_host = _prompt("Bridge SMTP host", config.DEFAULT_SMTP_HOST)
    smtp_port = _prompt_int("Bridge SMTP port", config.DEFAULT_SMTP_PORT)

    fingerprint = probe_fingerprint(imap_host, imap_port)
    print()
    print("Bridge TLS certificate fingerprint (SHA-256):")
    print(f"  {fingerprint}")
    print(
        "Compare this against Bridge → Settings → Show certificate → SHA-256."
    )
    confirm = _prompt("Pin this fingerprint? (y/n)", "y")
    if confirm.lower() not in {"y", "yes"}:
        print("aborted — fingerprint not confirmed", file=sys.stderr)
        return 1

    record = AccountRecord(
        label=label,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        bridge_password=bridge_password,
        tls_fingerprint_sha256=fingerprint,
    )

    try:
        _validate(record)
    except ProtonMcpError as e:
        print(f"error: validation failed: {e}", file=sys.stderr)
        return 1

    AccountStore().save(
        label=label,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        bridge_password=bridge_password,
        tls_fingerprint_sha256=fingerprint,
    )
    print(f"Saved account '{label}' (email: {email})")
    return 0


def _cmd_list() -> int:
    accounts = AccountStore().list()
    if not accounts:
        print("(no accounts configured)")
        return 0
    width = max(len(a.label) for a in accounts)
    for a in accounts:
        print(f"  {a.label.ljust(width)}  {a.email}")
    return 0


def _cmd_remove(label: str) -> int:
    try:
        AccountStore().remove(label)
    except AccountNotConfigured as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Removed account '{label}'")
    return 0


def _cmd_test(label: str) -> int:
    try:
        record = AccountStore().load(label)
        _validate(record)
    except ProtonMcpError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"OK — account '{label}' validates against Bridge")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proton-mcp-auth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="Authenticate and add a new account")
    p_add.add_argument("label", help="Local label (e.g. 'work', 'personal')")
    sub.add_parser("list", help="List configured accounts")
    p_rm = sub.add_parser("remove", help="Remove a configured account")
    p_rm.add_argument("label", help="Account label to remove")
    p_test = sub.add_parser(
        "test", help="Revalidate an existing account against Bridge"
    )
    p_test.add_argument("label", help="Account label to test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "add":
        return _cmd_add(args.label)
    if args.cmd == "list":
        return _cmd_list()
    if args.cmd == "remove":
        return _cmd_remove(args.label)
    if args.cmd == "test":
        return _cmd_test(args.label)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
