from __future__ import annotations

import hashlib
import ssl
from unittest.mock import MagicMock, patch

import pytest

from proton_mcp.accounts import AccountRecord
from proton_mcp.bridge import BridgeSession, fingerprint_sha256, pinned_ssl_context
from proton_mcp.exceptions import (
    BridgeNotRunning,
    BridgeRejectedCredentials,
    BridgeTLSMismatch,
)


def _record(fingerprint: str = "a" * 64) -> AccountRecord:
    return AccountRecord(
        label="work",
        email="alice@proton.me",
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        bridge_password="pw",
        tls_fingerprint_sha256=fingerprint,
    )


def test_fingerprint_sha256_returns_lowercase_hex():
    der_bytes = b"\x00\x01\x02fake-der"
    expected = hashlib.sha256(der_bytes).hexdigest()
    assert fingerprint_sha256(der_bytes) == expected
    assert fingerprint_sha256(der_bytes).islower()


def test_pinned_ssl_context_disables_hostname_verify():
    ctx = pinned_ssl_context(expected_fingerprint="a" * 64)
    assert ctx.check_hostname is False
    assert ctx.verify_mode == ssl.CERT_NONE


def test_imap_login_failure_maps_to_rejected_credentials():
    from imapclient.exceptions import LoginError

    fake_client = MagicMock()
    cert_bytes = b"the-real-cert"
    fake_client._sock.getpeercert.return_value = cert_bytes
    fake_client.login.side_effect = LoginError("bad password")
    expected = hashlib.sha256(cert_bytes).hexdigest()

    with patch("proton_mcp.bridge.IMAPClient", return_value=fake_client):
        with pytest.raises(BridgeRejectedCredentials) as excinfo:
            BridgeSession(_record(fingerprint=expected)).imap()
        assert "work" in str(excinfo.value)


def test_imap_connection_refused_maps_to_bridge_not_running():
    with patch(
        "proton_mcp.bridge.IMAPClient",
        side_effect=ConnectionRefusedError(),
    ):
        with pytest.raises(BridgeNotRunning) as excinfo:
            BridgeSession(_record()).imap()
        assert "127.0.0.1:1143" in str(excinfo.value)


def test_imap_socket_timeout_maps_to_bridge_not_running():
    with patch(
        "proton_mcp.bridge.IMAPClient",
        side_effect=TimeoutError("connect timed out"),
    ):
        with pytest.raises(BridgeNotRunning):
            BridgeSession(_record()).imap()


def test_imap_fingerprint_mismatch_maps_to_tls_mismatch():
    """If the server's cert sha256 doesn't match what's pinned, fail loudly."""
    fake_client = MagicMock()
    bad_der = b"different-cert-bytes"
    fake_client._sock.getpeercert.return_value = bad_der
    expected = hashlib.sha256(b"the-real-cert").hexdigest()

    with patch("proton_mcp.bridge.IMAPClient", return_value=fake_client):
        with pytest.raises(BridgeTLSMismatch) as excinfo:
            BridgeSession(_record(fingerprint=expected)).imap()
        assert "work" in str(excinfo.value)


def test_imap_success_returns_logged_in_client():
    fake_client = MagicMock()
    cert_bytes = b"the-real-cert"
    fake_client._sock.getpeercert.return_value = cert_bytes
    expected = hashlib.sha256(cert_bytes).hexdigest()

    with patch("proton_mcp.bridge.IMAPClient", return_value=fake_client):
        client = BridgeSession(_record(fingerprint=expected)).imap()

    assert client is fake_client
    fake_client.login.assert_called_once_with("alice@proton.me", "pw")


def test_smtp_connection_refused_maps_to_bridge_not_running():
    with patch(
        "proton_mcp.bridge.smtplib.SMTP",
        side_effect=ConnectionRefusedError(),
    ):
        with pytest.raises(BridgeNotRunning) as excinfo:
            BridgeSession(_record()).smtp()
        assert "127.0.0.1:1025" in str(excinfo.value)


def test_smtp_auth_failure_maps_to_rejected_credentials():
    import smtplib

    fake_smtp = MagicMock()
    fake_smtp.login.side_effect = smtplib.SMTPAuthenticationError(535, b"nope")
    fake_smtp.sock.getpeercert.return_value = b"cert"
    expected = hashlib.sha256(b"cert").hexdigest()

    with patch(
        "proton_mcp.bridge.smtplib.SMTP", return_value=fake_smtp
    ):
        with pytest.raises(BridgeRejectedCredentials):
            BridgeSession(_record(fingerprint=expected)).smtp()


def test_smtp_fingerprint_mismatch_maps_to_tls_mismatch():
    fake_smtp = MagicMock()
    fake_smtp.sock.getpeercert.return_value = b"unexpected-cert"
    expected = hashlib.sha256(b"the-real-cert").hexdigest()

    with patch(
        "proton_mcp.bridge.smtplib.SMTP", return_value=fake_smtp
    ):
        with pytest.raises(BridgeTLSMismatch):
            BridgeSession(_record(fingerprint=expected)).smtp()
