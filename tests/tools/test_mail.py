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


def test_mail_search_builds_imap_criteria_from_dict(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1700000001}
    imap.search.return_value = [42, 43]
    imap.fetch.return_value = {
        42: {
            b"FLAGS": (b"\\Seen",),
            b"RFC822.HEADER": (
                b"From: a@b\r\nTo: c@d\r\nSubject: hello\r\n"
                b"Date: Tue, 19 May 2026 12:00:00 +0000\r\n"
                b"Message-ID: <42@proton>\r\n\r\n"
            ),
        },
        43: {
            b"FLAGS": (),
            b"RFC822.HEADER": (
                b"From: e@f\r\nTo: g@h\r\nSubject: world\r\n"
                b"Date: Tue, 19 May 2026 12:01:00 +0000\r\n"
                b"Message-ID: <43@proton>\r\n\r\n"
            ),
        },
    }

    hits = mail_tools.mail_search(
        account="work",
        query={"from": "a@b", "subject": "hello", "since": "2026-05-01"},
        folder="INBOX",
        max_results=10,
    )

    assert len(hits) == 2
    handles = {h["handle"] for h in hits}
    assert handles == {"INBOX:1700000001:42", "INBOX:1700000001:43"}

    search_call = imap.search.call_args
    criteria = search_call.args[0] if search_call.args else search_call.kwargs["criteria"]
    assert "FROM" in criteria
    assert "a@b" in criteria
    assert "SUBJECT" in criteria
    assert "hello" in criteria
    assert "SINCE" in criteria


def test_mail_search_max_results_clamps_uid_list(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.search.return_value = [10, 11, 12, 13, 14]
    imap.fetch.return_value = {
        uid: {
            b"FLAGS": (),
            b"RFC822.HEADER": (
                b"From: x@y\r\nTo: z@y\r\nSubject: s\r\n"
                b"Date: \r\nMessage-ID: <" + str(uid).encode() + b"@p>\r\n\r\n"
            ),
        }
        for uid in [12, 13, 14]
    }

    hits = mail_tools.mail_search(
        account="work",
        query={},
        folder="INBOX",
        max_results=3,
    )

    assert len(hits) == 3
    fetched_uids = imap.fetch.call_args.args[0]
    assert sorted(fetched_uids) == [12, 13, 14]


def test_mail_search_empty_query_uses_imap_all(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.search.return_value = []
    imap.fetch.return_value = {}

    mail_tools.mail_search(
        account="work", query={}, folder="INBOX", max_results=10
    )

    criteria = imap.search.call_args.args[0]
    assert criteria == ["ALL"]
