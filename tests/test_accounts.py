from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from proton_mcp.accounts import AccountInfo, AccountStore
from proton_mcp.exceptions import AccountNotConfigured, InvalidAccountLabel
from tests.conftest import write_account_file


def test_list_returns_empty_when_no_accounts(tmp_config_dir: Path):
    assert AccountStore().list() == []


def test_list_returns_label_and_email_for_each_account(tmp_config_dir: Path):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    write_account_file(tmp_config_dir / "accounts", "personal", "bob@proton.me")

    result = sorted(AccountStore().list(), key=lambda a: a.label)
    assert result == [
        AccountInfo(label="personal", email="bob@proton.me"),
        AccountInfo(label="work", email="alice@proton.me"),
    ]


def test_save_writes_token_file_chmod_600(tmp_config_dir: Path):
    AccountStore().save(
        label="work",
        email="alice@proton.me",
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        bridge_password="pw",
        tls_fingerprint_sha256="a" * 64,
    )
    path = tmp_config_dir / "accounts" / "work.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["email"] == "alice@proton.me"
    assert data["bridge_password"] == "pw"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_load_returns_account_record(tmp_config_dir: Path):
    write_account_file(
        tmp_config_dir / "accounts",
        "work",
        "alice@proton.me",
        bridge_password="my-pw",
        tls_fingerprint="b" * 64,
    )
    rec = AccountStore().load("work")
    assert rec.label == "work"
    assert rec.email == "alice@proton.me"
    assert rec.imap_host == "127.0.0.1"
    assert rec.imap_port == 1143
    assert rec.smtp_host == "127.0.0.1"
    assert rec.smtp_port == 1025
    assert rec.bridge_password == "my-pw"
    assert rec.tls_fingerprint_sha256 == "b" * 64


def test_load_raises_when_label_unknown(tmp_config_dir: Path):
    with pytest.raises(AccountNotConfigured) as excinfo:
        AccountStore().load("nope")
    assert "nope" in str(excinfo.value)


def test_remove_deletes_token_file(tmp_config_dir: Path):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    AccountStore().remove("work")
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_remove_raises_when_label_unknown(tmp_config_dir: Path):
    with pytest.raises(AccountNotConfigured):
        AccountStore().remove("nope")


@pytest.mark.parametrize(
    "evil_label",
    [
        "../escape",
        "../../etc/passwd",
        "subdir/leak",
        "back\\slash",
        ".hidden",
        "..",
        "",
        "has space",
        "a" * 65,
    ],
)
def test_save_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().save(
            label=evil_label,
            email="x@y.com",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    "evil_label", ["../escape", "subdir/leak", ".hidden", ".."]
)
def test_load_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().load(evil_label)


@pytest.mark.parametrize(
    "evil_label", ["../escape", "subdir/leak", ".hidden", ".."]
)
def test_remove_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().remove(evil_label)


def test_save_does_not_create_files_outside_accounts_dir(tmp_config_dir: Path):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().save(
            label="../../../tmp/leaked",
            email="x@y.com",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )
    assert not (tmp_config_dir.parent / "tmp" / "leaked.json").exists()


def test_save_leaves_no_temp_files_behind(tmp_config_dir: Path):
    AccountStore().save(
        label="work",
        email="a@b.com",
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        bridge_password="pw",
        tls_fingerprint_sha256="c" * 64,
    )
    leftovers = list((tmp_config_dir / "accounts").glob("*.tmp.*"))
    assert leftovers == []


def test_atomic_write_creates_temp_file_with_mode_0600_under_permissive_umask(
    tmp_config_dir: Path,
):
    """Temp file must be created with restrictive perms from the START.

    Forces umask 022 and patches os.chmod to a no-op, so the only way the
    final mode can be 0o600 is if the file was opened with that mode in
    the first place.
    """
    captured_modes: list[int] = []
    real_replace = os.replace

    def probe_replace(src, dst):
        captured_modes.append(os.stat(src).st_mode & 0o777)
        return real_replace(src, dst)

    old_umask = os.umask(0o022)
    try:
        with patch("proton_mcp.accounts.os.chmod"), patch(
            "proton_mcp.accounts.os.replace", side_effect=probe_replace
        ):
            AccountStore().save(
                label="work",
                email="a@b.com",
                imap_host="127.0.0.1",
                imap_port=1143,
                smtp_host="127.0.0.1",
                smtp_port=1025,
                bridge_password="pw",
                tls_fingerprint_sha256="c" * 64,
            )
    finally:
        os.umask(old_umask)

    assert captured_modes == [0o600], (
        f"temp file was created with mode {captured_modes!r} — "
        "secrets exposed during the open->chmod window"
    )


def test_save_preserves_original_on_replace_error(tmp_config_dir: Path):
    """If atomic replace fails mid-way, an existing token must survive."""
    write_account_file(tmp_config_dir / "accounts", "work", "first@proton.me")
    original = (tmp_config_dir / "accounts" / "work.json").read_text()

    with patch(
        "proton_mcp.accounts.os.replace",
        side_effect=OSError("simulated"),
    ), pytest.raises(OSError):
        AccountStore().save(
            label="work",
            email="second@proton.me",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )

    assert (tmp_config_dir / "accounts" / "work.json").read_text() == original
