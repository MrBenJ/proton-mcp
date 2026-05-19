"""Paths, defaults, and size caps for the proton-mcp server."""

from __future__ import annotations

from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "proton-mcp"
ACCOUNTS_DIR = CONFIG_DIR / "accounts"

# Defaults match Proton Bridge's out-of-the-box configuration.
DEFAULT_IMAP_HOST = "127.0.0.1"
DEFAULT_IMAP_PORT = 1143
DEFAULT_SMTP_HOST = "127.0.0.1"
DEFAULT_SMTP_PORT = 1025

# Body text returned by mail_get_message is capped so a single huge message
# can't flood the conversation context. Truncated bodies are returned with
# a marker that records the original size so the agent can decide whether
# to widen the search or skip.
MAX_MAIL_BODY_BYTES = 256 * 1024

# Cap on attachment payloads (both download and outbound). 10 MiB covers
# everyday docs/images without letting a 200 MB video lock up stdio.
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024

# Hard cap on total outbound message size. Proton's SMTP allows 25 MiB.
MAX_OUTBOUND_BYTES = 25 * 1024 * 1024

# Hard cap on total inbound message size (RFC822.SIZE). Checked BEFORE
# we pull the bytes off the wire so a 200 MB email can't OOM us or hang
# the stdio transport. 25 MiB mirrors the outbound cap.
MAX_INBOUND_BYTES = 25 * 1024 * 1024
