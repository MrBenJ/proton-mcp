from __future__ import annotations

from email.message import EmailMessage

import pytest

from proton_mcp.shaping.mail import (
    MessageHandle,
    encode_handle,
    parse_handle,
    shape_attachment_list,
    shape_folder,
    shape_message_full,
    shape_message_summary,
    truncate_body,
)


def test_encode_handle_round_trip():
    h = MessageHandle(folder="INBOX", uidvalidity=1700000001, uid=42)
    encoded = encode_handle(h)
    assert encoded == "INBOX:1700000001:42"
    assert parse_handle(encoded) == h


def test_encode_handle_preserves_folder_with_special_chars():
    """IMAP folder names can contain slashes (hierarchy delimiter)."""
    h = MessageHandle(folder="Labels/My Custom", uidvalidity=1, uid=2)
    encoded = encode_handle(h)
    assert encoded == "Labels/My Custom:1:2"
    assert parse_handle(encoded) == h


def test_parse_handle_rejects_malformed():
    for bad in ["", "INBOX", "INBOX:1", "INBOX:abc:1", "INBOX:1:abc"]:
        with pytest.raises(ValueError):
            parse_handle(bad)


def test_shape_folder_recognizes_special_use_flags():
    f = shape_folder(
        flags=(b"\\Sent", b"\\HasNoChildren"),
        delimiter=b"/",
        name=b"Sent",
        message_count=42,
        unseen_count=3,
    )
    assert f["name"] == "Sent"
    assert f["path"] == "Sent"
    assert f["is_special"] is True
    assert f["special_kind"] == "sent"
    assert f["message_count"] == 42
    assert f["unseen_count"] == 3


def test_shape_folder_non_special_returns_none_kind():
    f = shape_folder(
        flags=(b"\\HasNoChildren",),
        delimiter=b"/",
        name=b"Receipts",
        message_count=0,
        unseen_count=0,
    )
    assert f["is_special"] is False
    assert f["special_kind"] is None


def test_shape_message_summary_extracts_headers():
    msg = EmailMessage()
    msg["From"] = "Alice <alice@proton.me>"
    msg["To"] = "Bob <bob@example.com>"
    msg["Subject"] = "Hello"
    msg["Date"] = "Tue, 19 May 2026 12:00:00 +0000"
    msg["Message-ID"] = "<abc@proton.me>"
    msg.set_content("body content")

    summary = shape_message_summary(
        msg,
        handle="INBOX:1:42",
        folder="INBOX",
        flags=(b"\\Seen",),
    )
    assert summary["handle"] == "INBOX:1:42"
    assert summary["message_id"] == "<abc@proton.me>"
    assert summary["from"] == "Alice <alice@proton.me>"
    assert summary["to"] == "Bob <bob@example.com>"
    assert summary["subject"] == "Hello"
    assert summary["date"] == "Tue, 19 May 2026 12:00:00 +0000"
    assert summary["folder"] == "INBOX"
    assert "\\Seen" in summary["flags"]
    assert "snippet" in summary


def test_shape_message_full_prefers_text_plain():
    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg.set_content("PLAIN BODY")
    msg.add_alternative("<p>html</p>", subtype="html")

    full = shape_message_full(msg, handle="INBOX:1:42", folder="INBOX", flags=())
    assert full["body_text"].strip() == "PLAIN BODY"


def test_shape_message_full_falls_back_to_stripped_html():
    """When only text/html is present, strip tags."""
    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg.set_content("<p>Hello <b>world</b></p>", subtype="html")

    full = shape_message_full(msg, handle="INBOX:1:42", folder="INBOX", flags=())
    assert "Hello world" in full["body_text"]
    assert "<p>" not in full["body_text"]


def test_shape_message_full_extracts_attachment_metadata():
    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg.set_content("body")
    msg.add_attachment(
        b"PDFCONTENT",
        maintype="application",
        subtype="pdf",
        filename="invoice.pdf",
    )

    full = shape_message_full(msg, handle="INBOX:1:42", folder="INBOX", flags=())
    assert len(full["attachments"]) == 1
    att = full["attachments"][0]
    assert att["filename"] == "invoice.pdf"
    assert att["mime"] == "application/pdf"
    assert att["size"] == len(b"PDFCONTENT")
    assert "attachment_id" in att


def test_shape_attachment_list_skips_parts_without_filename():
    """Parts without a filename (typical for inline images) aren't attachments.

    A multipart/alternative with text+html and no add_attachment call has
    zero parts that carry a filename, so the list must be empty even
    though the message has two body parts.
    """
    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg.set_content("body")
    msg.add_alternative("<p>hi</p>", subtype="html")

    atts = shape_attachment_list(msg)
    assert atts == []


def test_truncate_body_returns_short_text_unchanged():
    assert truncate_body("hello", cap=1024) == "hello"


def test_truncate_body_clips_with_marker_above_cap():
    big = "x" * 2000
    out = truncate_body(big, cap=100)
    assert out.startswith("x" * 100)
    assert "[...truncated:" in out
    assert "2000 bytes total" in out
