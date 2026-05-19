# proton-mcp

A local **Model Context Protocol** server that gives Claude Desktop access
to a user's **Proton Mail** account(s) through the official Proton Bridge.

Each tool call takes an explicit `account` label so the agent can operate
across multiple Proton accounts in the same conversation.

**Scope (v1):**
- Read: list folders, search (structured query), fetch full message, fetch attachment
- Write: send, create draft
- Modify: flags (\Seen, \Flagged, ...), move between folders, trash

**Designed for personal local use** on a single machine. Credentials live
under `~/.config/proton-mcp/`. Not for hosting or sharing.

---

## Prerequisites

- macOS, Linux, or WSL
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pipx`
- A **paid** Proton Mail plan — Proton Bridge requires it
- [Proton Mail Bridge](https://proton.me/mail/bridge) installed and signed
  into the account(s) you'll connect

---

## Quick install (let an agent do it)

If you have an AI agent running this repo locally (Claude Desktop, Claude
Code, etc.), you can ask it to install this server for you end-to-end —
including the Bridge setup:

> "Install this server. The runbook is in `agents/install/`."

Currently supported harnesses:

- **Claude Desktop** — [`agents/install/claude-desktop.md`](agents/install/claude-desktop.md)
- **Codex CLI** — coming in a follow-up.

For manual setup, see below.

---

## Manual install

### 1. Install Proton Mail Bridge

Download from <https://proton.me/mail/bridge>. Open the app, sign in with
your Proton account, and let it complete the initial sync.

### 2. Capture Bridge credentials

In the Bridge app, open the account view. You need:

- **Email address** (e.g. `alice@proton.me`)
- **Bridge IMAP/SMTP password** (a long random string Bridge generates —
  not your Proton login password)
- **IMAP host:port** (default `127.0.0.1:1143`)
- **SMTP host:port** (default `127.0.0.1:1025`)
- **TLS certificate SHA-256 fingerprint** — Bridge → Settings → "Show
  certificate" → SHA-256. The CLI shows the live fingerprint on first
  add; compare them character-for-character.

### 3. Install this server

```bash
# from a clone of this repo
uv tool install .
```

This puts two commands on your `PATH`:

- `proton-mcp` — the MCP server (started by Claude Desktop)
- `proton-mcp-auth` — manage local Bridge credentials

### 4. Add your first account

```bash
proton-mcp-auth add personal
```

You'll be prompted for the email, Bridge password, host/port pairs, and
asked to confirm the displayed certificate fingerprint matches what
Bridge shows. The CLI does a one-shot IMAP login to validate before
writing `~/.config/proton-mcp/accounts/personal.json`.

To add another account, repeat with a different label:

```bash
proton-mcp-auth add work
```

List, remove, or revalidate:

```bash
proton-mcp-auth list
proton-mcp-auth remove personal
proton-mcp-auth test personal
```

### 5. Wire into Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and
add (merging — don't clobber existing servers):

```json
{
  "mcpServers": {
    "proton": {
      "command": "/Users/<you>/.local/bin/proton-mcp"
    }
  }
}
```

Use the absolute path — Claude Desktop launched from Finder/Dock doesn't
inherit your shell PATH. Find it with `command -v proton-mcp`.

Cmd+Q Claude Desktop (not just close the window) and reopen. You should
see the tools listed; try:

> "Search my personal Proton inbox for unread mail from this week."

Claude will call `mail_search` with `account="personal"`.

---

## Verifying your setup

Add a dedicated test account (or use your personal one if you're brave)
and run the end-to-end smoke:

```bash
MCP_E2E_ACCOUNT=test-account uv run python scripts/e2e_smoke.py
```

The script boots the actual MCP server as a subprocess, sends a tagged
self-email, searches for it, fetches it, trashes it, then creates and
trashes a draft. Takes ~10–20 seconds.

---

## Troubleshooting

| Error | What it means | Fix |
|---|---|---|
| `Account 'work' not configured` | No token file for that label | `proton-mcp-auth add work` |
| `Cannot reach Bridge at 127.0.0.1:1143` | Bridge isn't running | Start Proton Mail Bridge and retry |
| `Bridge TLS fingerprint ... does not match` | Bridge regenerated its cert (reinstall, factory reset) | `proton-mcp-auth test work` will fail and you can re-pin via `proton-mcp-auth add work` |
| `Bridge rejected credentials` | Wrong password, or Bridge reset its app password | Open Bridge → copy the new password → `proton-mcp-auth add work` |
| `Message handle is stale (UIDVALIDITY changed)` | Folder was rebuilt server-side | Re-search and use the new handle |

## Project layout

See [`docs/superpowers/specs/2026-05-19-proton-mcp-design.md`](docs/superpowers/specs/2026-05-19-proton-mcp-design.md)
and [`docs/superpowers/plans/2026-05-19-proton-mcp.md`](docs/superpowers/plans/2026-05-19-proton-mcp.md)
for the design and step-by-step implementation history.
