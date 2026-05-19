from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

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


def test_mail_get_message_returns_shaped_full_message(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1700000001}

    raw = (
        b"From: alice@proton.me\r\n"
        b"To: bob@example.com\r\n"
        b"Subject: hello\r\n"
        b"Date: Tue, 19 May 2026 12:00:00 +0000\r\n"
        b"Message-ID: <42@proton>\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"PLAIN BODY"
    )
    imap.fetch.side_effect = [
        {42: {b"RFC822.SIZE": len(raw)}},
        {42: {b"FLAGS": (b"\\Seen",), b"RFC822": raw}},
    ]

    msg = mail_tools.mail_get_message(
        account="work", handle="INBOX:1700000001:42"
    )
    assert msg["handle"] == "INBOX:1700000001:42"
    assert msg["subject"] == "hello"
    assert msg["body_text"] == "PLAIN BODY"
    assert msg["attachments"] == []


def test_mail_get_message_refuses_when_rfc822_size_exceeds_inbound_cap(
    tmp_config_dir: Path, mock_bridge: dict, monkeypatch
):
    """The size precheck must run BEFORE the full RFC822 fetch.

    Mocks `fetch` so the first call returns RFC822.SIZE and the second
    would raise — verifying we never make the second call when the
    precheck rejects.
    """
    import pytest

    from proton_mcp import config as cfg
    from proton_mcp.exceptions import MessageTooLarge

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    monkeypatch.setattr(cfg, "MAX_INBOUND_BYTES", 1024)

    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.fetch.side_effect = [
        {1: {b"RFC822.SIZE": 5_000_000}},
        AssertionError("full RFC822 fetched despite oversize precheck"),
    ]

    with pytest.raises(MessageTooLarge) as excinfo:
        mail_tools.mail_get_message(account="work", handle="INBOX:1:1")
    assert excinfo.value.size == 5_000_000
    assert excinfo.value.cap == 1024
    assert imap.fetch.call_count == 1


def test_mail_get_message_stale_handle_raises(
    tmp_config_dir: Path, mock_bridge: dict
):
    import pytest

    from proton_mcp.exceptions import MessageHandleStale

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 9999}

    with pytest.raises(MessageHandleStale) as excinfo:
        mail_tools.mail_get_message(
            account="work", handle="INBOX:1700000001:42"
        )
    assert "INBOX:1700000001:42" in str(excinfo.value)


def test_mail_get_message_truncates_oversize_body(
    tmp_config_dir: Path, mock_bridge: dict, monkeypatch
):
    from proton_mcp import config as cfg

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    monkeypatch.setattr(cfg, "MAX_MAIL_BODY_BYTES", 50)

    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    big_body = "x" * 5000
    raw = (
        b"From: a@b\r\nTo: c@d\r\nSubject: big\r\n"
        b"Date: \r\nMessage-ID: <1@p>\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n\r\n"
        + big_body.encode()
    )
    imap.fetch.side_effect = [
        {1: {b"RFC822.SIZE": len(raw)}},
        {1: {b"FLAGS": (), b"RFC822": raw}},
    ]

    msg = mail_tools.mail_get_message(account="work", handle="INBOX:1:1")
    assert "[...truncated:" in msg["body_text"]
    assert "5000 bytes total" in msg["body_text"]


def test_mail_get_attachment_returns_base64_content(
    tmp_config_dir: Path, mock_bridge: dict
):
    import base64
    from email.message import EmailMessage

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}

    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg["Date"] = "Tue, 19 May 2026 12:00:00 +0000"
    msg["Message-ID"] = "<1@p>"
    msg.set_content("body")
    msg.add_attachment(
        b"PDFCONTENT", maintype="application", subtype="pdf", filename="invoice.pdf"
    )
    raw_bytes = bytes(msg)
    imap.fetch.return_value = {1: {b"FLAGS": (), b"RFC822": raw_bytes}}

    listed = mail_tools.mail_get_message(account="work", handle="INBOX:1:1")
    att_id = listed["attachments"][0]["attachment_id"]

    payload = mail_tools.mail_get_attachment(
        account="work", handle="INBOX:1:1", attachment_id=att_id
    )
    assert payload["filename"] == "invoice.pdf"
    assert payload["mime"] == "application/pdf"
    assert payload["size"] == len(b"PDFCONTENT")
    assert base64.b64decode(payload["content_b64"]) == b"PDFCONTENT"


def test_mail_get_attachment_oversize_raises(
    tmp_config_dir: Path, mock_bridge: dict, monkeypatch
):
    from email.message import EmailMessage

    import pytest

    from proton_mcp import config as cfg
    from proton_mcp.exceptions import AttachmentTooLarge

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    monkeypatch.setattr(cfg, "MAX_ATTACHMENT_BYTES", 5)

    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}

    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg["Date"] = ""
    msg["Message-ID"] = "<1@p>"
    msg.set_content("body")
    msg.add_attachment(
        b"BIG" * 100, maintype="application", subtype="pdf", filename="big.pdf"
    )
    imap.fetch.return_value = {1: {b"FLAGS": (), b"RFC822": bytes(msg)}}

    full = mail_tools.mail_get_message(account="work", handle="INBOX:1:1")
    att_id = full["attachments"][0]["attachment_id"]
    with pytest.raises(AttachmentTooLarge):
        mail_tools.mail_get_attachment(
            account="work", handle="INBOX:1:1", attachment_id=att_id
        )


def test_mail_send_submits_via_smtp_and_returns_message_id(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    smtp = mock_bridge["smtp"]

    result = mail_tools.mail_send(
        account="work",
        to="bob@example.com",
        subject="Hi Bob",
        body="hello",
    )

    assert "message_id" in result
    smtp.send_message.assert_called_once()
    sent_msg = smtp.send_message.call_args.args[0]
    assert sent_msg["To"] == "bob@example.com"
    assert sent_msg["Subject"] == "Hi Bob"
    assert sent_msg["From"] == "a@proton.me"
    assert mock_bridge["calls"][-1] == ("work", "smtp")


def test_mail_send_threading_headers(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    smtp = mock_bridge["smtp"]

    mail_tools.mail_send(
        account="work",
        to="bob@example.com",
        subject="Re: Hi",
        body="reply",
        in_reply_to="<orig@proton.me>",
    )

    sent_msg = smtp.send_message.call_args.args[0]
    assert sent_msg["In-Reply-To"] == "<orig@proton.me>"
    assert sent_msg["References"] == "<orig@proton.me>"


def test_mail_send_html_body_attaches_alternative(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    smtp = mock_bridge["smtp"]

    mail_tools.mail_send(
        account="work",
        to="bob@example.com",
        subject="HTML",
        body="<p>hello</p>",
        html=True,
    )

    sent_msg = smtp.send_message.call_args.args[0]
    assert sent_msg.is_multipart()
    types = [p.get_content_type() for p in sent_msg.walk() if not p.is_multipart()]
    assert "text/html" in types


def test_mail_send_attachments_are_decoded_and_attached(
    tmp_config_dir: Path, mock_bridge: dict
):
    import base64

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    smtp = mock_bridge["smtp"]

    mail_tools.mail_send(
        account="work",
        to="bob@example.com",
        subject="With file",
        body="body",
        attachments=[
            {
                "filename": "note.txt",
                "mime": "text/plain",
                "content_b64": base64.b64encode(b"file content").decode(),
            }
        ],
    )

    sent_msg = smtp.send_message.call_args.args[0]
    attached = [
        p for p in sent_msg.walk()
        if not p.is_multipart() and p.get_filename() == "note.txt"
    ]
    assert len(attached) == 1
    assert attached[0].get_payload(decode=True) == b"file content"


def test_mail_send_rejects_oversize_message(
    tmp_config_dir: Path, mock_bridge: dict, monkeypatch
):
    import base64

    import pytest

    from proton_mcp import config as cfg
    from proton_mcp.exceptions import OutboundTooLarge

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    monkeypatch.setattr(cfg, "MAX_OUTBOUND_BYTES", 100)

    with pytest.raises(OutboundTooLarge):
        mail_tools.mail_send(
            account="work",
            to="bob@example.com",
            subject="big",
            body="x",
            attachments=[
                {
                    "filename": "big.bin",
                    "mime": "application/octet-stream",
                    "content_b64": base64.b64encode(b"y" * 5000).decode(),
                }
            ],
        )


def test_mail_create_draft_appends_to_drafts_folder(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.list_folders.return_value = [
        ((b"\\HasNoChildren",), b"/", "INBOX"),
        ((b"\\Drafts", b"\\HasNoChildren"), b"/", "Drafts"),
    ]

    result = mail_tools.mail_create_draft(
        account="work",
        to="bob@example.com",
        subject="draft",
        body="draft body",
    )

    assert "message_id" in result
    imap.append.assert_called_once()
    folder, raw_bytes, flags, _date = imap.append.call_args.args
    assert folder == "Drafts"
    assert b"draft body" in raw_bytes
    assert b"\\Draft" in flags


def test_mail_modify_flags_adds_and_removes_seen(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.get_flags.return_value = {42: (b"\\Seen", b"\\Flagged")}

    result = mail_tools.mail_modify_flags(
        account="work",
        handle="INBOX:1:42",
        add_flags=["\\Flagged"],
        remove_flags=["\\Seen"],
    )

    imap.add_flags.assert_called_once_with([42], [b"\\Flagged"])
    imap.remove_flags.assert_called_once_with([42], [b"\\Seen"])
    assert "\\Flagged" in result["flags"]


def test_mail_modify_flags_stale_handle_raises(
    tmp_config_dir: Path, mock_bridge: dict
):
    import pytest

    from proton_mcp.exceptions import MessageHandleStale

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 9999}

    with pytest.raises(MessageHandleStale):
        mail_tools.mail_modify_flags(
            account="work", handle="INBOX:1:42", add_flags=["\\Seen"]
        )


def test_mail_move_message_uses_move_when_advertised(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.side_effect = lambda cap: cap == "MOVE"
    imap.move = MagicMock()

    result = mail_tools.mail_move_message(
        account="work", handle="INBOX:1:42", dest_folder="Archive"
    )

    imap.move.assert_called_once_with([42], "Archive")
    assert result["moved_to"] == "Archive"


def test_mail_move_message_uses_uid_expunge_fallback_when_uidplus_available(
    tmp_config_dir: Path, mock_bridge: dict
):
    """No MOVE capability but UIDPLUS present: COPY + \\Deleted + UID EXPUNGE.

    Crucially the expunge must be scoped to the specific UID — a plain
    EXPUNGE would purge any other \\Deleted messages in the folder.
    """
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.side_effect = lambda cap: cap == "UIDPLUS"

    mail_tools.mail_move_message(
        account="work", handle="INBOX:1:42", dest_folder="Archive"
    )

    imap.copy.assert_called_once_with([42], "Archive")
    imap.add_flags.assert_called_once_with([42], [b"\\Deleted"])
    imap.expunge.assert_called_once_with(messages=[42])


def test_mail_move_message_refuses_when_no_move_and_no_uidplus(
    tmp_config_dir: Path, mock_bridge: dict
):
    """Neither MOVE nor UIDPLUS — refuse rather than risk a broad EXPUNGE."""
    import pytest

    from proton_mcp.exceptions import ProtonMcpError

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.return_value = False

    with pytest.raises(ProtonMcpError) as excinfo:
        mail_tools.mail_move_message(
            account="work", handle="INBOX:1:42", dest_folder="Archive"
        )
    assert "UIDPLUS" in str(excinfo.value)
    imap.expunge.assert_not_called()


def test_mail_trash_moves_to_special_trash_folder(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.side_effect = lambda cap: cap == "MOVE"
    imap.list_folders.return_value = [
        ((b"\\HasNoChildren",), b"/", "INBOX"),
        ((b"\\Trash", b"\\HasNoChildren"), b"/", "Trash"),
    ]

    result = mail_tools.mail_trash(account="work", handle="INBOX:1:42")
    imap.move.assert_called_once_with([42], "Trash")
    assert result["moved_to"] == "Trash"
