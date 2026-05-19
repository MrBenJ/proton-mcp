# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this is

A local stdio MCP server exposing Proton Mail tools to a single user via
Proton Bridge, with **multi-account routing**: every tool call takes an
`account` label (e.g. `"work"`, `"personal"`) and the server resolves it
to the matching Bridge credentials under
`~/.config/proton-mcp/accounts/<label>.json`. Designed for personal local
use only — not for hosting.

## Commands

Dependencies are managed with `uv`:

- `uv sync` — install dev + runtime deps into `.venv`
- `uv run pytest` — unit test suite (mocks Bridge; no network)
- `uv run pytest tests/tools/test_mail.py::test_name` — single test
- `uv run pytest tests/shaping` — only shaping tests
- `uv run ruff check .` — lint (line length 100, py311)
- `uv run mypy` — strict type-check
- `uv tool install .` — install `proton-mcp` and `proton-mcp-auth`
- `MCP_E2E_ACCOUNT=<label> uv run python scripts/e2e_smoke.py` — opt-in
  live smoke that drives the real server over stdio against Bridge.

CI runs `ruff`, `mypy`, and `pytest` on every push/PR to `main`.

## Architecture

### Two entry points

- `proton_mcp.server:main` — stdio MCP server. Builds an `mcp.server.Server`,
  registers tools from `TOOL_REGISTRY`, runs over `mcp.server.stdio`.
- `proton_mcp.auth_cli:main` — `add` / `list` / `remove` / `test` CLI that
  validates credentials against Bridge before persisting.

### The `TOOL_REGISTRY` pattern (`src/proton_mcp/server.py`)

All tool definitions live in a single list of `{name, description, schema,
handler}` dicts. `build_app()` enumerates this list for both `list_tools`
and `call_tool`. **Adding a tool means appending one dict here.** Handler
signature: `lambda args: tool_module.fn(**args)`, so JSON-schema property
names must match the underlying function's kwargs exactly.

`_invoke_tool` is the error funnel: every handler call is wrapped and
failures convert to a stable `"error: ..."` text payload — `ProtonMcpError`
verbatim, `ValueError`/`TypeError` as "invalid arguments", anything else
as "internal error". The MCP transport never sees a Python exception.
`_dispatch` is indirected from `_invoke_tool` so tests can patch one
symbol to simulate every error category. Preserve this convention.

### Layering: `tools/` vs `shaping/`

- `tools/mail.py` — calls IMAP/SMTP via `BridgeSession`, hands raw RFC822
  bytes or `imapclient` dicts to shaping.
- `shaping/mail.py` — pure functions that compact RFC822 into the small
  dicts returned to the model. **Keep IMAP/SMTP calls out of `shaping/`**
  and keep payload-massaging out of `tools/`; shaping tests in
  `tests/shaping/` rely on this split.

### Bridge connection layer (`bridge.py`)

`BridgeSession` is the single boundary between the tool layer and the
network. Per tool call, the tool function builds `BridgeSession(record)`,
calls `.imap()` or `.smtp()`, and `.logout()`/`.quit()` in a `finally`.
No global connection cache.

TLS is **pinned** per account via a SHA-256 fingerprint stored in the
account file. Bridge presents a self-signed cert with no SAN on
`127.0.0.1`, so stdlib chain verification is bypassed and replaced with a
post-handshake fingerprint compare. A mismatch raises `BridgeTLSMismatch`
which surfaces to the agent with a "re-pin via `proton-mcp-auth test`"
hint.

### Credentials (`accounts.py`)

- One JSON file per account under `config.ACCOUNTS_DIR`
  (`~/.config/proton-mcp/accounts/`).
- Labels validated against `^[A-Za-z0-9_-]{1,64}$` — **path-traversal
  guard**, do not loosen.
- Writes go through `_atomic_write_json`: `os.open` with `O_CREAT|O_EXCL|
  O_WRONLY` + mode `0o600`, then `os.replace`. The Bridge password must
  never be momentarily world-readable.
- `_file_lock` (fcntl flock on a sidecar `.lock`) guards concurrent
  reads/writes between the server and the auth CLI.

### Message handles

Tools return and accept a composite handle `folder:uidvalidity:uid`
(string) because IMAP UIDs are folder-scoped. If a folder's UIDVALIDITY
shifts (rare with Bridge), operations using the old handle surface as
`MessageHandleStale` instead of silently operating on the wrong message.

### Attachment IDs

`shape_attachment_list` returns each attachment with a stable
`attachment_id` (SHA-256 of position+filename+content-id, first 16 hex
chars) and an internal `_part_index`. `mail_get_message` strips the
internal field before returning. `mail_get_attachment` re-walks the
message and matches on `_part_index` to find the actual payload bytes.
If you change the walk order in shaping, the cached IDs become useless —
keep the part-walk deterministic.

### Size caps (`config.py`)

- `MAX_MAIL_BODY_BYTES` (256 KiB) — `mail_get_message` truncates with a
  marker that records the original byte count.
- `MAX_ATTACHMENT_BYTES` (10 MiB) — checked against `BODYSTRUCTURE` before
  the payload is fetched.
- `MAX_OUTBOUND_BYTES` (25 MiB) — checked before SMTP submit.

## Testing layout

- `tests/conftest.py` — `tmp_config_dir` redirects `config.CONFIG_DIR`
  and `ACCOUNTS_DIR` to a tmp path; `write_account_file` helper drops a
  fake token file; `mock_bridge` patches `BridgeSession` in
  `tools.mail` and returns the inner IMAP/SMTP MagicMocks.
- `tests/tools/test_mail.py` — drive tool functions with the mocked
  Bridge; assert IMAP/SMTP calls and JSON shapes.
- `tests/shaping/test_mail.py` — pure-data tests on shaping helpers; no
  mocks needed.
- `scripts/e2e_smoke.py` — the only thing that touches a real Bridge.
  Not part of `pytest`; run manually before releases.

## Conventions

- Strict mypy (`disallow_untyped_defs` etc. via `strict = true`). Library
  boundaries (`imapclient`, `mcp`) are exempt via `[[tool.mypy.overrides]]`.
- Ruff selects `E, F, W, I, B, UP` — py311+ syntax.
- `from __future__ import annotations` at the top of every module.
- The MCP transport sees only JSON strings or `"error: ..."` strings —
  never raise out of a tool handler.
