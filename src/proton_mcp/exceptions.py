"""Errors surfaced to MCP tool callers."""

from __future__ import annotations


class ProtonMcpError(Exception):
    """Base class for all proton-mcp errors."""


class AccountNotConfigured(ProtonMcpError):
    def __init__(self, label: str) -> None:
        super().__init__(
            f"Account '{label}' not configured. Run: proton-mcp-auth add {label}"
        )
        self.label = label


class InvalidAccountLabel(ProtonMcpError):
    """Labels must match a strict slug pattern; anything else risks path
    traversal into the account-token directory."""

    def __init__(self, label: str) -> None:
        super().__init__(
            f"Invalid account label {label!r}. Labels must be 1-64 chars "
            "from [a-zA-Z0-9_-] only."
        )
        self.label = label


class BridgeNotRunning(ProtonMcpError):
    def __init__(self, host: str, port: int) -> None:
        super().__init__(
            f"Cannot reach Bridge at {host}:{port}. "
            "Start Proton Mail Bridge and retry."
        )
        self.host = host
        self.port = port


class BridgeTLSMismatch(ProtonMcpError):
    def __init__(self, label: str) -> None:
        super().__init__(
            f"Bridge TLS fingerprint for account '{label}' does not match the "
            f"pinned value. Run: proton-mcp-auth test {label}"
        )
        self.label = label


class BridgeRejectedCredentials(ProtonMcpError):
    def __init__(self, label: str) -> None:
        super().__init__(
            f"Bridge rejected credentials for account '{label}'. "
            f"Re-add the account: proton-mcp-auth add {label}"
        )
        self.label = label


class MessageHandleStale(ProtonMcpError):
    def __init__(self, handle: str) -> None:
        super().__init__(
            f"Message handle '{handle}' is stale (UIDVALIDITY changed). "
            "Re-search and retry."
        )
        self.handle = handle


class AttachmentTooLarge(ProtonMcpError):
    def __init__(self, *, size: int, cap: int) -> None:
        super().__init__(
            f"Attachment too large: {size} bytes exceeds cap of {cap} bytes."
        )
        self.size = size
        self.cap = cap


class OutboundTooLarge(ProtonMcpError):
    def __init__(self, *, size: int, cap: int) -> None:
        super().__init__(
            f"Outbound message too large: {size} bytes exceeds cap of {cap} bytes."
        )
        self.size = size
        self.cap = cap
