from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from proton_mcp.auth_cli import main
from tests.conftest import write_account_file


def _stub_inputs(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    answers_iter = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers_iter))
    monkeypatch.setattr("getpass.getpass", lambda *a, **kw: next(answers_iter))


def test_add_persists_account_after_validation_succeeds(
    tmp_config_dir: Path, monkeypatch, capsys
):
    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "bridge-pw",
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "y",
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )
    fake_session = MagicMock()
    fake_session.imap.return_value = MagicMock()
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["add", "work"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Saved account 'work'" in out
    data = json.loads(
        (tmp_config_dir / "accounts" / "work.json").read_text()
    )
    assert data["bridge_password"] == "bridge-pw"
    assert data["tls_fingerprint_sha256"] == "f" * 64


def test_add_aborts_if_user_declines_fingerprint(
    tmp_config_dir: Path, monkeypatch, capsys
):
    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "pw",
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "n",
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )

    rc = main(["add", "work"])
    assert rc != 0
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_add_does_not_persist_on_validation_failure(
    tmp_config_dir: Path, monkeypatch, capsys
):
    from proton_mcp.exceptions import BridgeRejectedCredentials

    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "wrong-pw",
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "y",
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )
    fake_session = MagicMock()
    fake_session.imap.side_effect = BridgeRejectedCredentials("work")
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["add", "work"])
    assert rc != 0
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_list_prints_label_and_email_rows(
    tmp_config_dir: Path, capsys
):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    write_account_file(tmp_config_dir / "accounts", "personal", "bob@proton.me")

    rc = main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "work" in out
    assert "alice@proton.me" in out
    assert "personal" in out
    assert "bob@proton.me" in out


def test_list_prints_placeholder_when_no_accounts(
    tmp_config_dir: Path, capsys
):
    rc = main(["list"])
    assert rc == 0
    assert "no accounts configured" in capsys.readouterr().out


def test_remove_deletes_token_file(tmp_config_dir: Path, capsys):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    rc = main(["remove", "work"])
    assert rc == 0
    assert "Removed account 'work'" in capsys.readouterr().out
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_remove_unknown_label_exits_nonzero(tmp_config_dir: Path):
    rc = main(["remove", "nope"])
    assert rc != 0


def test_test_command_revalidates_existing_account(
    tmp_config_dir: Path, monkeypatch, capsys
):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    fake_session = MagicMock()
    fake_session.imap.return_value = MagicMock()
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["test", "work"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out
