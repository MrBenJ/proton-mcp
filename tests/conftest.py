from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config.CONFIG_DIR (and ACCOUNTS_DIR) to a tmp dir."""
    from proton_mcp import config

    tmp_cfg = tmp_path / "proton-mcp"
    tmp_accounts = tmp_cfg / "accounts"
    tmp_cfg.mkdir()
    tmp_accounts.mkdir()

    monkeypatch.setattr(config, "CONFIG_DIR", tmp_cfg)
    monkeypatch.setattr(config, "ACCOUNTS_DIR", tmp_accounts)
    return tmp_cfg


def write_account_file(
    accounts_dir: Path,
    label: str,
    email: str,
    *,
    bridge_password: str = "br1dg3-app-pw",
    tls_fingerprint: str = "a" * 64,
) -> Path:
    """Drop a token file on disk for tests that need an existing account."""
    path = accounts_dir / f"{label}.json"
    path.write_text(
        json.dumps(
            {
                "label": label,
                "email": email,
                "imap_host": "127.0.0.1",
                "imap_port": 1143,
                "smtp_host": "127.0.0.1",
                "smtp_port": 1025,
                "bridge_password": bridge_password,
                "tls_fingerprint_sha256": tls_fingerprint,
            }
        )
    )
    return path


@pytest.fixture
def mock_bridge(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch BridgeSession used by proton_mcp.tools.mail.

    Returns a dict with:
        "imap":  MagicMock standing in for IMAPClient
        "smtp":  MagicMock standing in for smtplib.SMTP
        "calls": list of (label, "imap"|"smtp") to assert routing
    """
    import importlib

    imap = MagicMock(name="IMAPClient")
    smtp = MagicMock(name="SMTP")
    calls: list[tuple[str, str]] = []

    class FakeSession:
        def __init__(self, record):
            self._record = record

        def imap(self):
            calls.append((self._record.label, "imap"))
            return imap

        def smtp(self):
            calls.append((self._record.label, "smtp"))
            return smtp

    try:
        mod = importlib.import_module("proton_mcp.tools.mail")
    except ImportError:
        return {
            "imap": imap,
            "smtp": smtp,
            "calls": calls,
            "FakeSession": FakeSession,
        }
    monkeypatch.setattr(mod, "BridgeSession", FakeSession)
    return {
        "imap": imap,
        "smtp": smtp,
        "calls": calls,
        "FakeSession": FakeSession,
    }
