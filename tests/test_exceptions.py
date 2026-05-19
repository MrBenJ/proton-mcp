from __future__ import annotations

from proton_mcp.exceptions import (
    AccountNotConfigured,
    AttachmentTooLarge,
    BridgeNotRunning,
    BridgeRejectedCredentials,
    BridgeTLSMismatch,
    InvalidAccountLabel,
    MessageHandleStale,
    OutboundTooLarge,
    ProtonMcpError,
)


def test_all_errors_inherit_from_base():
    for cls in (
        AccountNotConfigured,
        InvalidAccountLabel,
        BridgeNotRunning,
        BridgeTLSMismatch,
        BridgeRejectedCredentials,
        MessageHandleStale,
        AttachmentTooLarge,
        OutboundTooLarge,
    ):
        assert issubclass(cls, ProtonMcpError)


def test_account_not_configured_message_includes_label_and_command():
    err = AccountNotConfigured("work")
    assert "work" in str(err)
    assert "proton-mcp-auth add work" in str(err)
    assert err.label == "work"


def test_invalid_account_label_message_and_attribute():
    err = InvalidAccountLabel("../oops")
    assert "../oops" in str(err)
    assert err.label == "../oops"


def test_bridge_not_running_message_includes_endpoint():
    err = BridgeNotRunning("127.0.0.1", 1143)
    assert "127.0.0.1:1143" in str(err)
    assert "Start Proton Mail Bridge" in str(err)


def test_bridge_tls_mismatch_message_points_to_test_command():
    err = BridgeTLSMismatch("work")
    assert "proton-mcp-auth test work" in str(err)


def test_bridge_rejected_credentials_message_points_to_add_command():
    err = BridgeRejectedCredentials("work")
    assert "proton-mcp-auth add work" in str(err)


def test_message_handle_stale_carries_handle_string():
    err = MessageHandleStale("INBOX:1700000000:42")
    assert "INBOX:1700000000:42" in str(err)
    assert err.handle == "INBOX:1700000000:42"


def test_attachment_too_large_includes_byte_counts():
    err = AttachmentTooLarge(size=20_000_000, cap=10_485_760)
    assert "20000000" in str(err)
    assert "10485760" in str(err)
    assert err.size == 20_000_000
    assert err.cap == 10_485_760


def test_outbound_too_large_includes_byte_counts():
    err = OutboundTooLarge(size=30_000_000, cap=26_214_400)
    assert "30000000" in str(err)
    assert "26214400" in str(err)
