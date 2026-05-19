from __future__ import annotations

import json
from pathlib import Path

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
