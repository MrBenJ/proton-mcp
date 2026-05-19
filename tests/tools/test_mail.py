from __future__ import annotations

from pathlib import Path

from proton_mcp.tools import mail as mail_tools
from tests.conftest import write_account_file


def test_list_accounts_returns_label_and_email(tmp_config_dir: Path):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    write_account_file(tmp_config_dir / "accounts", "personal", "b@proton.me")

    result = sorted(mail_tools.list_accounts(), key=lambda r: r["label"])
    assert result == [
        {"label": "personal", "email": "b@proton.me"},
        {"label": "work", "email": "a@proton.me"},
    ]


def test_mail_list_folders_returns_shaped_rows(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.list_folders.return_value = [
        ((b"\\HasNoChildren",), b"/", "INBOX"),
        ((b"\\Sent", b"\\HasNoChildren"), b"/", "Sent"),
        ((b"\\Trash", b"\\HasNoChildren"), b"/", "Trash"),
    ]
    imap.folder_status.side_effect = [
        {b"MESSAGES": 10, b"UNSEEN": 2},
        {b"MESSAGES": 7, b"UNSEEN": 0},
        {b"MESSAGES": 0, b"UNSEEN": 0},
    ]

    folders = mail_tools.mail_list_folders(account="work")

    assert [f["name"] for f in folders] == ["INBOX", "Sent", "Trash"]
    assert folders[1]["special_kind"] == "sent"
    assert folders[2]["special_kind"] == "trash"
    assert folders[0]["message_count"] == 10
    assert folders[0]["unseen_count"] == 2
    assert mock_bridge["calls"] == [("work", "imap")]
