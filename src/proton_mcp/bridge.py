"""IMAP + SMTP session helpers with TLS pinning against Proton Bridge."""

from __future__ import annotations

import hashlib
import imaplib
import smtplib
import socket
import ssl
from typing import TYPE_CHECKING

from imapclient import IMAPClient
from imapclient.exceptions import LoginError

from proton_mcp.exceptions import (
    BridgeNotRunning,
    BridgeRejectedCredentials,
    BridgeTLSMismatch,
)

if TYPE_CHECKING:
    from proton_mcp.accounts import AccountRecord


def fingerprint_sha256(der_bytes: bytes) -> str:
    """Lowercase hex SHA-256 of a DER-encoded certificate."""
    return hashlib.sha256(der_bytes).hexdigest()


def pinned_ssl_context(*, expected_fingerprint: str) -> ssl.SSLContext:
    """Return an SSL context that doesn't pre-verify (the actual check is
    done after handshake by comparing the peer cert SHA-256 against the
    pinned value).

    Bridge presents a self-signed cert with no SAN for 127.0.0.1, so we
    cannot use stdlib's standard chain verification. The certificate is
    *unique per Bridge install*, so the per-account pin in the account
    record is the trust anchor.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


class BridgeSession:
    """One Bridge session for one account. Build per tool call.

    The session is intentionally not pooled; localhost handshakes are
    sub-ms and stdio tool calls are infrequent enough that the simplicity
    of build-per-call dominates.
    """

    def __init__(self, record: AccountRecord) -> None:
        self._record = record

    def imap(self) -> IMAPClient:
        """Return a logged-in IMAPClient connected to Bridge.

        Tries implicit TLS (ssl=True) first; if the TLS handshake fails
        (Bridge configured for STARTTLS), falls back to plaintext +
        STARTTLS upgrade. Maps network failure → BridgeNotRunning, TLS
        mismatch → BridgeTLSMismatch, auth failure →
        BridgeRejectedCredentials.
        """
        rec = self._record
        ctx = pinned_ssl_context(expected_fingerprint=rec.tls_fingerprint_sha256)

        # --- implicit TLS (Bridge SSL/TLS mode) ---
        try:
            client = IMAPClient(
                host=rec.imap_host,
                port=rec.imap_port,
                ssl=True,
                ssl_context=ctx,
                timeout=10,
            )
            peer_der = client._sock.getpeercert(binary_form=True)
        except ssl.SSLError:
            # --- STARTTLS fallback (Bridge STARTTLS mode) ---
            try:
                client = IMAPClient(
                    host=rec.imap_host,
                    port=rec.imap_port,
                    ssl=False,
                    timeout=10,
                )
                client.starttls(ssl_context=ctx)
            except (ConnectionRefusedError, TimeoutError, OSError) as e:
                raise BridgeNotRunning(rec.imap_host, rec.imap_port) from e
            peer_der = client._imap.socket().getpeercert(binary_form=True)
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            raise BridgeNotRunning(rec.imap_host, rec.imap_port) from e

        if peer_der is None or fingerprint_sha256(peer_der) != rec.tls_fingerprint_sha256:
            raise BridgeTLSMismatch(rec.label)

        try:
            client.login(rec.email, rec.bridge_password)
        except LoginError as e:
            raise BridgeRejectedCredentials(rec.label) from e
        return client

    def smtp(self) -> smtplib.SMTP:
        """Return a STARTTLS'd + logged-in SMTP client."""
        rec = self._record
        try:
            smtp = smtplib.SMTP(rec.smtp_host, rec.smtp_port, timeout=10)
            smtp.ehlo()
            smtp.starttls(
                context=pinned_ssl_context(
                    expected_fingerprint=rec.tls_fingerprint_sha256
                )
            )
            smtp.ehlo()
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            raise BridgeNotRunning(rec.smtp_host, rec.smtp_port) from e

        # After STARTTLS, smtp.sock is an ssl.SSLSocket; mypy sees the base
        # socket type and can't tell. Narrow via getattr.
        get_cert = getattr(smtp.sock, "getpeercert", None)
        if get_cert is None:
            raise BridgeTLSMismatch(rec.label)
        peer_der = get_cert(True)
        if peer_der is None or fingerprint_sha256(peer_der) != rec.tls_fingerprint_sha256:
            raise BridgeTLSMismatch(rec.label)

        try:
            smtp.login(rec.email, rec.bridge_password)
        except smtplib.SMTPAuthenticationError as e:
            raise BridgeRejectedCredentials(rec.label) from e
        return smtp


def probe_fingerprint(host: str, port: int, *, timeout: float = 10.0) -> str:
    """One-shot TLS handshake to <host>:<port>, return server cert SHA-256.

    Used by the auth CLI on `add` to display the Bridge fingerprint for
    user TOFU confirmation. Tries implicit TLS first (Bridge SSL/TLS mode);
    falls back to STARTTLS via imaplib if the direct wrap fails (Bridge
    STARTTLS mode). The SMTP cert is the same identity as IMAP.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    # Try implicit TLS first
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls:
                der = tls.getpeercert(binary_form=True)
        if der is None:
            raise BridgeNotRunning(host, port)
        return fingerprint_sha256(der)
    except ssl.SSLError:
        pass

    # Fall back to STARTTLS (Bridge STARTTLS connection mode)
    try:
        conn = imaplib.IMAP4(host, port)
        conn.starttls(ssl_context=ctx)
        der = conn.socket().getpeercert(binary_form=True)
        try:
            conn.logout()
        except Exception:
            pass
    except (ConnectionRefusedError, TimeoutError, OSError) as e:
        raise BridgeNotRunning(host, port) from e
    if der is None:
        raise BridgeNotRunning(host, port)
    return fingerprint_sha256(der)
