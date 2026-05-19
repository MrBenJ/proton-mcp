# Proton MCP Server — Design

**Date:** 2026-05-19
**Status:** Draft, pending user review
**Target clients:** Claude Desktop (v1); Codex CLI deferred to a follow-up
**Scope:** Personal use on a single machine — not published, single user

---

## 1. Goal

A local stdio MCP server that lets Claude Desktop retrieve, view, and edit a
user's Proton Mail through Claude's cowork interface. Same multi-account
ergonomics as the sibling `multi-google-mcp` project: every tool call takes an
`account` label and the server resolves it to local credentials under
`~/.config/proton-mcp/accounts/<label>.json`.

This spec covers Claude Desktop only. The same server binary will work
unchanged under Codex CLI once a separate install runbook is written.

## 2. Non-goals (v1)

- Multi-user / multi-machine deployment, hosting, or a remote MCP broker.
- Encrypted ProtonDrive, ProtonCalendar, ProtonPass, ProtonVPN integrations.
- Background sync, local search index, or message caching.
- Permanent delete (use Trash; user can empty Trash in the Proton UI).
- Retry / backoff policies — IMAP and SMTP errors surface verbatim.
- Free-tier Proton accounts (Bridge requires a paid Proton plan; see §13).
- PGP key management, signing, or external-recipient encryption — Bridge
  handles internal Proton-to-Proton encryption transparently.

## 3. Stack

- Python 3.11+, packaged with `uv` (consistent with `multi-google-mcp`).
- `mcp` Python SDK over stdio.
- `imapclient` — higher-level IMAP than stdlib `imaplib`, preserves UID
  semantics cleanly.
- Stdlib `smtplib` + `email.message.EmailMessage` for outbound.
- Test stack: `pytest`, `ruff`, `mypy --strict`.

`imapclient` is chosen over stdlib `imaplib` because `imaplib` returns
byte-tuples that have to be re-parsed for every command; `imapclient` returns
parsed dicts (`fetch` → `{uid: {b'FLAGS': (...), b'RFC822': b'...'}}`) which
maps directly onto our shaping layer.

## 4. Repository layout

```
proton-mcp/
├── pyproject.toml
├── README.md                                # Bridge setup + Claude Desktop wiring
├── CLAUDE.md                                # Repo orientation for future Claude sessions
├── LICENSE
├── docs/superpowers/specs/
│   └── 2026-05-19-proton-mcp-design.md      # this file
├── src/proton_mcp/
│   ├── __init__.py
│   ├── server.py                            # MCP entrypoint, TOOL_REGISTRY
│   ├── auth_cli.py                          # proton-mcp-auth add|list|remove|test
│   ├── accounts.py                          # AccountStore: per-label JSON
│   ├── bridge.py                            # IMAP/SMTP connection helpers + TLS pin
│   ├── config.py                            # paths, defaults, body-size caps
│   ├── exceptions.py                        # ProtonMcpError hierarchy
│   ├── tools/
│   │   ├── __init__.py
│   │   └── mail.py                          # all mail tool functions
│   └── shaping/
│       ├── __init__.py
│       └── mail.py                          # RFC822 → compact JSON
├── tests/
│   ├── conftest.py
│   ├── test_accounts.py
│   ├── test_auth_cli.py
│   ├── test_bridge.py
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_server.py
│   ├── tools/
│   │   └── test_mail.py
│   └── shaping/
│       └── test_mail.py
├── scripts/
│   └── e2e_smoke.py                         # opt-in real Bridge smoke
└── agents/install/
    └── claude-desktop.md                    # phased install runbook
```

## 5. Auth and storage

### 5.1 One-time user setup (documented in README and install runbook)

1. Install **Proton Mail Bridge** from <https://proton.me/mail/bridge>.
2. Open Bridge, sign in with the Proton account, allow it to sync.
3. Bridge generates an app password and exposes IMAP on
   `127.0.0.1:1143` and SMTP on `127.0.0.1:1025` by default. Both speak
   STARTTLS with a self-signed cert that is unique to the Bridge install.
4. From Bridge: copy the SMTP/IMAP credentials and TLS certificate
   fingerprint.

The install runbook walks the user through every step interactively.

### 5.2 On-disk layout

```
~/.config/proton-mcp/
└── accounts/
    ├── personal.json
    └── work.json
```

There is no shared `client_secret.json` — Bridge is the auth boundary, not
OAuth. Per-label file shape:

```json
{
  "label": "personal",
  "email": "alice@proton.me",
  "imap_host": "127.0.0.1",
  "imap_port": 1143,
  "smtp_host": "127.0.0.1",
  "smtp_port": 1025,
  "bridge_password": "<app-password from Bridge>",
  "tls_fingerprint_sha256": "<hex>"
}
```

All files written with `chmod 0o600` via the same `O_CREAT|O_EXCL|O_WRONLY`
+ atomic-replace pattern as `multi_google_mcp.accounts._atomic_write_json`.
A sidecar `<label>.json.lock` (fcntl flock) guards concurrent reads/writes.
The slug regex `^[A-Za-z0-9_-]{1,64}$` is the path-traversal guard — copied
verbatim from the Google project.

### 5.3 Auth CLI

`proton-mcp-auth`:

- `add <label>` — interactive prompts:
  - email (e.g. `alice@proton.me`)
  - bridge password (read via `getpass`, never echoed)
  - IMAP host/port (defaults `127.0.0.1:1143`)
  - SMTP host/port (defaults `127.0.0.1:1025`)
  - TLS fingerprint (auto-fetched on first connect; stored after confirming
    with user — Trust-On-First-Use)
  - After save, performs a `CAPABILITY` + `LOGIN` round-trip and a
    `noop`-style SMTP `EHLO` to validate credentials before persisting.
- `list` — prints `(label, email, imap_host:port, smtp_host:port)` rows.
- `remove <label>` — deletes the token file.
- `test <label>` — re-runs the connect/validate check on an existing
  account (handy when Bridge has been reset).

### 5.4 TLS to localhost Bridge

Bridge presents a self-signed certificate that is unique per install. Two
approaches were considered:

- **Disable verification** (`ssl.CERT_NONE`). Easy, but throws away the
  defense against another process on `127.0.0.1` listening on `:1143` and
  MITM-ing credentials.
- **Pin the certificate fingerprint** (chosen). On first `add`, fetch the
  peer cert, compute SHA-256, show it to the user, ask them to confirm
  against Bridge's "Show certificate" panel, then store the fingerprint in
  the account file. Future connects verify against the pinned fingerprint.

Bridge regenerates its cert when reinstalled or factory-reset; in that case
the user reruns `proton-mcp-auth test <label>` which detects the mismatch
and prompts re-pinning.

## 6. Tool surface

10 tools total. Every operational tool takes `account: str`. Each tool
returns compact JSON — never raw RFC822 byte blobs.

### 6.1 Discovery (1)

| Tool | Returns |
|---|---|
| `list_accounts()` | `[{"label": "personal", "email": "alice@proton.me"}, ...]` |

### 6.2 Mail read (4)

| Tool | Notes |
|---|---|
| `mail_list_folders(account)` | `[{name, path, is_special, special_kind?}]`. Recognizes Proton's All Mail / Sent / Drafts / Trash / Archive / Spam by IMAP `\Sent`, `\Drafts`, etc. SPECIAL-USE flags. |
| `mail_search(account, query, folder="INBOX", max_results=20)` | `query` is a small structured dict: `{from, to, subject, text, since, before, seen, flagged}`. Builds IMAP `SEARCH` keywords. Returns `[{handle, message_id, from, to, subject, snippet, date, flags, folder}]`. |
| `mail_get_message(account, handle)` | Full headers + best-effort text body + attachment metadata. Body capped at `MAX_MAIL_BODY_BYTES` with a truncation marker. |
| `mail_get_attachment(account, handle, attachment_id)` | Base64 payload + `{filename, mime, size}`. Hard-capped at `MAX_ATTACHMENT_BYTES`. |

### 6.3 Mail write (2)

| Tool | Notes |
|---|---|
| `mail_send(account, to, subject, body, cc?, bcc?, html=false, in_reply_to?, attachments?)` | Submits via Bridge SMTP. `attachments` is `[{filename, mime, content_b64}]`. `in_reply_to` populates `In-Reply-To`/`References` headers. |
| `mail_create_draft(account, to, subject, body, ...)` | Same shape as `send` minus the SMTP submit; appends to Bridge's `Drafts` folder via IMAP `APPEND`. |

### 6.4 Mail modify (3)

| Tool | Notes |
|---|---|
| `mail_modify_flags(account, handle, add_flags?, remove_flags?)` | Standard IMAP flags only: `\Seen`, `\Flagged`, `\Answered`, `\Draft`. Proton's user labels are surfaced as IMAP folders (not keywords), so labelling a message means moving/copying it with `mail_move_message`. |
| `mail_move_message(account, handle, dest_folder)` | Uses IMAP `MOVE` (RFC 6851) when Bridge advertises it; falls back to `COPY`+`STORE \Deleted`+`EXPUNGE` otherwise. |
| `mail_trash(account, handle)` | Convenience: `move` to Proton's Trash folder, resolved via SPECIAL-USE. |

### 6.5 Message handle format

IMAP UIDs are folder-scoped, so a bare integer is ambiguous across folders.
The handle returned to the model is a string:

```
<folder>:<uidvalidity>:<uid>
```

e.g. `INBOX:1700000001:42`. Tools parse this into a `MessageHandle`
dataclass internally. `UIDVALIDITY` is included so a folder reset
(rare with Bridge but possible) surfaces as an explicit
`MessageHandleStale` error rather than silently operating on the wrong
message. The shaped message dict also includes the `Message-ID` header so
the agent can cross-reference messages between folders if needed.

### 6.6 Token-budget estimate

10 tools × ~190 tokens average ≈ **~1.9k tokens** of tool schema per
conversation. Cached by Claude Desktop's prompt caching after turn 1.

## 7. Bridge connection layer (`bridge.py`)

Single boundary between the tool layer and the network:

```python
class BridgeSession:
    """Lazy IMAP + SMTP clients for one account, with TLS pinning."""

    def imap(self) -> IMAPClient: ...    # logged in, IDLE-capable
    def smtp(self) -> smtplib.SMTP: ...  # STARTTLS'd, EHLO'd, logged in
    def close(self) -> None: ...
```

- Built per tool call via `BridgeSession.for_account(label)`; no global
  connection cache (matches Google project's per-call service build).
- IMAP `LOGIN` uses `bridge_password`; same for SMTP `AUTH LOGIN`.
- TLS context is built with `create_default_context()` then overridden to
  pin via a `check_hostname=False`, custom verify callback that compares
  the peer DER's SHA-256 against `tls_fingerprint_sha256`. Hostname
  verification is intentionally off because the cert is for `127.0.0.1`
  with no SAN.
- Connection errors map to `BridgeNotRunning` (ECONNREFUSED) or
  `BridgeTLSMismatch` (fingerprint diff) so the tool layer can surface
  actionable messages.

Why not a connection pool? Per-call latency to `127.0.0.1` is sub-ms; the
complexity of keeping IMAP sessions warm across stdio-tool invocations
(reconnection, IDLE timeout) isn't worth it for v1. Revisit if profiling
shows per-call SSL handshakes dominating.

## 8. Data flow (per tool call)

1. Claude Desktop calls the tool over stdio.
2. `_invoke_tool` resolves the registry entry and runs the handler.
3. Handler builds `BridgeSession.for_account(account)`.
4. Handler calls IMAP/SMTP via the session; raw bytes / `imapclient` dicts
   come back.
5. Result passes through `shaping/mail.py` → compact dict.
6. Session closed; result JSON-serialized and returned.

## 9. Error handling

All operational failures convert to `"error: <message>"` strings in
`_invoke_tool`. The MCP transport never sees an exception. Categories,
matching the Google project:

| Condition | Surfaced as |
|---|---|
| Unknown label | `"error: account 'X' not configured. Run: proton-mcp-auth add X"` |
| Bridge not running | `"error: cannot reach Bridge at 127.0.0.1:1143. Start Proton Mail Bridge and retry."` |
| TLS fingerprint mismatch | `"error: Bridge TLS fingerprint changed. Run: proton-mcp-auth test X"` |
| Bad bridge password | `"error: Bridge rejected credentials. Re-add account: proton-mcp-auth add X"` |
| Stale message handle | `"error: message handle is stale (UIDVALIDITY changed). Re-search and retry."` |
| Folder not found | `"error: folder 'Foo' not found. Use mail_list_folders to discover names."` |
| Oversize body / attachment | `ProtonMcpError` subclass with the byte counts |
| Bad arguments | `"error: invalid arguments: <Exception>: <msg>"` |
| Anything else | `"error: internal error: <Exception>: <msg>"` |

## 10. Response shaping

Mirrors the Google project's philosophy: tools return compact dicts, never
raw payloads. Key shapes:

- **Folder:** `{name, path, is_special, special_kind, message_count, unseen_count}`
- **Message summary (from search):** `{handle, message_id, from, to, cc, subject, snippet, date, flags, folder}`
- **Message full:** summary + `{body_text, body_html_stripped?, attachments: [{attachment_id, filename, mime, size}]}`
- **Attachment payload:** `{filename, mime, size, content_b64}`
- **Send/draft result:** `{message_id}` (Message-ID header of the sent/drafted mail)

`body_text` extraction: prefer `text/plain`; fall back to a stripped
`text/html` (no anchor URLs preserved — kept simple; revisit if the model
asks for links explicitly).

## 11. Size caps (`config.py`)

- `MAX_MAIL_BODY_BYTES = 256 * 1024` — same as Gmail. Bodies over the cap
  are truncated with `[...truncated: <N> bytes total, showing first <K>]`.
- `MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024` — same as Drive. Attachment
  size is checked from the IMAP `BODYSTRUCTURE` *before* fetching the
  payload; if oversize, `mail_get_attachment` returns an error rather than
  downloading.
- `MAX_OUTBOUND_BYTES = 25 * 1024 * 1024` — refuses send if total message
  (body + attachments) exceeds. Proton's actual SMTP limit is 25 MB.

## 12. Testing

### 12.1 Unit tests (always-on, no network)

- `tests/conftest.py` — `tmp_config_dir` fixture redirecting
  `config.CONFIG_DIR`; `saved_account` fixture dropping a fake account
  JSON; `mock_bridge` patches `bridge.BridgeSession` for tool tests.
- `tests/test_accounts.py` — load/save/remove/path-traversal-guard tests.
- `tests/test_bridge.py` — TLS pinning logic against a stub SSL socket;
  error-mapping tests.
- `tests/tools/test_mail.py` — every tool against a mocked
  `IMAPClient`/`SMTP`; asserts the IMAP commands issued and the shape of
  the JSON returned.
- `tests/shaping/test_mail.py` — RFC822 → dict shaping, with hand-rolled
  fixture emails for plain, HTML-only, multipart-alternative, and
  multipart-mixed-with-attachments cases.

### 12.2 End-to-end smoke (opt-in)

`scripts/e2e_smoke.py` — single script, runs against a real Bridge with a
test Proton account. Opt-in via env var:

```
MCP_E2E_ACCOUNT=test-account uv run python scripts/e2e_smoke.py
```

**Level 1 — Real Bridge round-trips:**

- Send self-email with unique tag in subject.
- Search Inbox for the tag → fetch message → assert body matches.
- Move to a temp `proton-mcp-smoke` folder, then back, then to Trash.
- Create a draft, assert it appears in Drafts, delete it.

Idempotent — every artifact carries a `proton-mcp-smoke-<uuid>` tag and is
cleaned up in `try/finally`, including on partial failure.

**Level 2 — MCP transport round-trip:**

Spawns the actual `proton-mcp` server as a subprocess and drives it over
stdio via the MCP Python client. Verifies tool registration, schema
validation, and stdio framing.

Runs in ~20 seconds. Documented in README under "Verifying your setup."

## 13. Free-tier / Bridge-less mode

Bridge requires a paid Proton plan. For free-tier users, two future paths
exist (out of scope for v1):

- **hydroxide** — community open-source IMAP/SMTP bridge. Same protocol
  surface; would slot into `bridge.py` with different defaults. The same
  `accounts/<label>.json` shape works.
- **Direct Proton API** — SRP login + downloading encrypted ciphertexts +
  PGP decrypt in-process. High maintenance burden; rejected.

v1 documents the paid-plan requirement plainly in the README and install
runbook so users aren't surprised.

## 14. Install runbook (Claude Desktop)

`agents/install/claude-desktop.md` mirrors the structure of
`multi-google-mcp/agents/install/claude-desktop.md`:

- **Phase 0 — Preflight:** detect Bridge install, `uv`, `proton-mcp` CLI,
  at least one account, Claude Desktop config presence, server already
  wired.
- **Phase 1 — Install Proton Bridge.** Walk the user through downloading
  from `proton.me/mail/bridge`, opening the app, signing in with their
  Proton account, and waiting for the initial sync to complete. Branch
  for users on a free plan: clear "you'll need to upgrade to use Bridge"
  message, exit ramp.
- **Phase 2 — Capture Bridge credentials.** Walk the user to Bridge's
  account view, copy the IMAP/SMTP password, copy the host/port pairs,
  copy the TLS fingerprint from Bridge's "Show certificate" panel.
- **Phase 3 — Install `uv`.** Same one-liner as the Google runbook.
- **Phase 4 — Install the CLI.** `uv tool install .` from the repo root.
- **Phase 5 — Add the account.** `proton-mcp-auth add <label>`,
  validating credentials before persisting.
- **Phase 6 — Wire into Claude Desktop config.** Same read-merge-write
  with absolute-path resolution (`command -v proton-mcp`) and timestamped
  backup as the Google runbook. The PATH-vs-GUI gotcha applies identically.
- **Phase 7 — Verify and restart.** Cmd+Q Claude Desktop, reopen, ask it
  to "search my personal Proton inbox for unread mail."

Codex CLI install runbook is deliberately deferred per user direction.
The server itself runs unchanged under Codex; only the runbook differs.

## 15. README structure

1. What this is.
2. Prerequisites (Python 3.11+, `uv`, paid Proton plan, Proton Mail Bridge).
3. Bridge setup (with prose for each Bridge screen).
4. Install (`uv tool install .`).
5. Add your first account (`proton-mcp-auth add personal`).
6. Wire into Claude Desktop.
7. Verifying your setup (E2E smoke).
8. Adding more accounts.
9. Removing / rotating accounts.
10. Troubleshooting:
    - `cannot reach Bridge at 127.0.0.1:1143` → start Bridge.
    - `Bridge TLS fingerprint changed` → re-pin via `proton-mcp-auth test`.
    - `Bridge rejected credentials` → regenerate app password in Bridge.
    - Free-plan user hitting the Bridge wall.

## 16. Conventions (carried over verbatim from `multi-google-mcp`)

- Strict mypy (`strict = true`), Ruff `E, F, W, I, B, UP`, `from __future__
  import annotations` everywhere, `py311+` syntax.
- The MCP transport sees only JSON strings or `"error: ..."` strings —
  never raise an exception out of a tool handler.
- Tool docstrings short and model-facing; long-form rationale lives in
  CLAUDE.md.
- One JSON file per account; refresh-token-equivalent (the
  `bridge_password`) protected by `0o600` + atomic write + fcntl flock.

## 17. Open questions resolved by this spec

- **Which Proton integration path?** Bridge over IMAP/SMTP (§3, §5, §13).
- **How do we identify messages across folders?** Composite handle
  `folder:uidvalidity:uid` + Message-ID header (§6.5).
- **How do we handle Bridge's self-signed cert?** TOFU pin sha256
  fingerprint, stored per account (§5.4, §7).
- **What's in v1 vs deferred?** v1 = Claude Desktop + paid plan. Deferred
  = Codex runbook, free-tier hydroxide path, Proton Calendar/Drive.
- **What size caps?** 256 KiB body / 10 MiB attachment / 25 MiB outbound (§11).

## 18. Out of scope for v1 (intentional)

- Proton Calendar / Proton Drive / Proton Pass / Proton VPN — separate
  surfaces, separate spec.
- Encrypted-to-external recipient (Proton's "expiring encrypted email" flow).
- IMAP `IDLE` for push notifications / streaming new mail.
- Server-side filter management (Proton's Sieve rules) — Bridge does not
  expose this over IMAP.
- Custom domains, alias management, hide-my-email — Proton-account-admin
  surface, not mail-data surface.
- Codex CLI install runbook (will follow in v1.1).
