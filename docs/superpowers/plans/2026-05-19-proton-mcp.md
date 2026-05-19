# Proton MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local stdio MCP server that lets Claude Desktop retrieve, view, and edit a user's Proton Mail (over the official Proton Bridge), with per-account credentials stored under `~/.config/proton-mcp/`.

**Architecture:** Python 3.11+ project packaged with `uv`. One process exposes 10 MCP tools over stdio (1 discovery + 4 read + 2 write + 3 modify). Every operational tool takes an explicit `account: str` arg routing to a per-label JSON file on disk that holds the Bridge IMAP/SMTP credentials and a pinned TLS fingerprint. A standalone CLI manages the per-account record outside the server.

**Tech Stack:** Python 3.11+, `uv`, `mcp` Python SDK (stdio), `imapclient` for IMAP, stdlib `smtplib` + `email` for SMTP/outbound, `pytest`, `ruff`, `mypy --strict`.

**Spec:** `docs/superpowers/specs/2026-05-19-proton-mcp-design.md`

---

## File Structure

```
proton-mcp/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── LICENSE
├── .gitignore
├── .github/workflows/ci.yml
├── docs/superpowers/
│   ├── specs/2026-05-19-proton-mcp-design.md   (already exists)
│   └── plans/2026-05-19-proton-mcp.md          (this file)
├── src/proton_mcp/
│   ├── __init__.py
│   ├── config.py             # paths, defaults, size caps
│   ├── exceptions.py         # ProtonMcpError hierarchy
│   ├── accounts.py           # AccountStore
│   ├── bridge.py             # BridgeSession (IMAP+SMTP with TLS pinning)
│   ├── auth_cli.py           # proton-mcp-auth CLI
│   ├── server.py             # MCP entrypoint + TOOL_REGISTRY
│   ├── shaping/
│   │   ├── __init__.py
│   │   └── mail.py           # RFC822 → compact JSON
│   └── tools/
│       ├── __init__.py
│       └── mail.py           # all mail tools
├── tests/
│   ├── __init__.py
│   ├── conftest.py           # shared fixtures
│   ├── test_config.py
│   ├── test_exceptions.py
│   ├── test_accounts.py
│   ├── test_bridge.py
│   ├── test_auth_cli.py
│   ├── test_server.py
│   ├── shaping/
│   │   ├── __init__.py
│   │   └── test_mail.py
│   └── tools/
│       ├── __init__.py
│       └── test_mail.py
├── scripts/
│   └── e2e_smoke.py
└── agents/install/
    └── claude-desktop.md
```

---

## Phase A — Foundations

### Task 1: Initialize repository and commit the spec

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: Initialize git repo**

Run from `/Users/bjunya/code/proton-mcp`:

```bash
git init
git branch -M main
```

Expected: `Initialized empty Git repository`.

- [ ] **Step 2: Write `.gitignore`**

Create `.gitignore`:

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.venv/
venv/
.mypy_cache/
.ruff_cache/
.pytest_cache/
dist/
build/

# Project
accounts/
*.local
.env
```

- [ ] **Step 3: Commit the spec + plan + gitignore**

```bash
git add .gitignore docs/superpowers/specs/2026-05-19-proton-mcp-design.md docs/superpowers/plans/2026-05-19-proton-mcp.md
git commit -m "docs: initial spec and implementation plan for proton-mcp"
```

Expected: a single commit holding the spec, plan, and gitignore.

---

### Task 2: Scaffold the Python project

**Files:**
- Create: `pyproject.toml`
- Create: `LICENSE`
- Create: `src/proton_mcp/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/shaping/__init__.py`
- Create: `tests/tools/__init__.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "proton-mcp"
version = "0.1.0"
description = "Local MCP server for Proton Mail over Proton Bridge"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "imapclient>=3.0.0",
]

[project.scripts]
proton-mcp = "proton_mcp.server:main"
proton-mcp-auth = "proton_mcp.auth_cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/proton_mcp"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra -q"
pythonpath = ["src"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "B", "UP"]

[tool.mypy]
strict = true
python_version = "3.11"
mypy_path = "src"
packages = ["proton_mcp"]

# These libraries don't ship a py.typed marker; trust them at the boundary.
[[tool.mypy.overrides]]
module = ["imapclient.*", "mcp.*"]
ignore_missing_imports = true
disallow_untyped_calls = false
disallow_untyped_decorators = false

[dependency-groups]
dev = [
    "pytest>=8.0.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]
```

- [ ] **Step 2: Write `LICENSE` (MIT)**

Create `LICENSE`:

```
MIT License

Copyright (c) 2026 The proton-mcp authors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create package `__init__.py` files**

`src/proton_mcp/__init__.py`:

```python
"""proton-mcp: local MCP server for Proton Mail via Proton Bridge."""
```

`tests/__init__.py`, `tests/shaping/__init__.py`, `tests/tools/__init__.py` are all empty files. Create them.

- [ ] **Step 4: Install dependencies with uv**

```bash
uv sync
```

Expected: `.venv/` created, dependencies installed. If `uv` is missing, install via `curl -LsSf https://astral.sh/uv/install.sh | sh` first.

- [ ] **Step 5: Verify lint and type-check pass on an empty project**

```bash
uv run ruff check .
uv run mypy
```

Expected: both succeed with "no issues."

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml LICENSE src/proton_mcp/__init__.py tests/__init__.py tests/shaping/__init__.py tests/tools/__init__.py uv.lock
git commit -m "chore: scaffold Python project with uv + ruff + mypy"
```

---

### Task 3: Implement `config.py` with tests

**Files:**
- Create: `src/proton_mcp/config.py`
- Create: `tests/test_config.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write the failing test for `config.py` constants**

Create `tests/test_config.py`:

```python
from __future__ import annotations

from pathlib import Path

from proton_mcp import config


def test_config_dir_is_under_user_config():
    assert config.CONFIG_DIR == Path.home() / ".config" / "proton-mcp"


def test_accounts_dir_is_under_config_dir():
    assert config.ACCOUNTS_DIR == config.CONFIG_DIR / "accounts"


def test_default_bridge_endpoints_are_localhost():
    assert config.DEFAULT_IMAP_HOST == "127.0.0.1"
    assert config.DEFAULT_IMAP_PORT == 1143
    assert config.DEFAULT_SMTP_HOST == "127.0.0.1"
    assert config.DEFAULT_SMTP_PORT == 1025


def test_size_caps_match_spec():
    assert config.MAX_MAIL_BODY_BYTES == 256 * 1024
    assert config.MAX_ATTACHMENT_BYTES == 10 * 1024 * 1024
    assert config.MAX_OUTBOUND_BYTES == 25 * 1024 * 1024
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
uv run pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'proton_mcp.config'` or similar import failure.

- [ ] **Step 3: Implement `config.py`**

Create `src/proton_mcp/config.py`:

```python
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
```

- [ ] **Step 4: Add the `tmp_config_dir` fixture in `conftest.py`**

Create `tests/conftest.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def tmp_config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect config.CONFIG_DIR (and ACCOUNTS_DIR) to a tmp dir."""
    from proton_mcp import config

    tmp_cfg = tmp_path / "proton-mcp"
    tmp_accounts = tmp_cfg / "accounts"
    tmp_cfg.mkdir()
    tmp_accounts.mkdir()

    monkeypatch.setattr(config, "CONFIG_DIR", tmp_cfg)
    monkeypatch.setattr(config, "ACCOUNTS_DIR", tmp_accounts)
    return tmp_cfg


def write_account_file(
    accounts_dir: Path,
    label: str,
    email: str,
    *,
    bridge_password: str = "br1dg3-app-pw",
    tls_fingerprint: str = "a" * 64,
) -> Path:
    """Drop a token file on disk for tests that need an existing account."""
    path = accounts_dir / f"{label}.json"
    path.write_text(
        json.dumps(
            {
                "label": label,
                "email": email,
                "imap_host": "127.0.0.1",
                "imap_port": 1143,
                "smtp_host": "127.0.0.1",
                "smtp_port": 1025,
                "bridge_password": bridge_password,
                "tls_fingerprint_sha256": tls_fingerprint,
            }
        )
    )
    return path
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_config.py -v
uv run ruff check .
uv run mypy
```

Expected: 4 passes, lint and mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/proton_mcp/config.py tests/test_config.py tests/conftest.py
git commit -m "feat(config): paths, defaults, and size caps"
```

---

### Task 4: Implement `exceptions.py` with tests

**Files:**
- Create: `src/proton_mcp/exceptions.py`
- Create: `tests/test_exceptions.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_exceptions.py`:

```python
from __future__ import annotations

import pytest

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_exceptions.py -v
```

Expected: `ImportError` — `proton_mcp.exceptions` doesn't exist yet.

- [ ] **Step 3: Implement `exceptions.py`**

Create `src/proton_mcp/exceptions.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_exceptions.py -v
uv run ruff check .
uv run mypy
```

Expected: 9 passes, lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/exceptions.py tests/test_exceptions.py
git commit -m "feat(exceptions): ProtonMcpError hierarchy"
```

---

## Phase B — Account storage

### Task 5: Implement `AccountStore` (accounts.py)

**Files:**
- Create: `src/proton_mcp/accounts.py`
- Create: `tests/test_accounts.py`

The pattern is the same as `multi_google_mcp/accounts.py`: per-label JSON files written atomically with `O_CREAT|O_EXCL|O_WRONLY` mode `0o600` + `os.replace`, with a `fcntl.flock` sidecar lock. The slug regex prevents path traversal.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_accounts.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

from proton_mcp.accounts import AccountInfo, AccountStore
from proton_mcp.exceptions import AccountNotConfigured, InvalidAccountLabel
from tests.conftest import write_account_file


def test_list_returns_empty_when_no_accounts(tmp_config_dir: Path):
    assert AccountStore().list() == []


def test_list_returns_label_and_email_for_each_account(tmp_config_dir: Path):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    write_account_file(tmp_config_dir / "accounts", "personal", "bob@proton.me")

    result = sorted(AccountStore().list(), key=lambda a: a.label)
    assert result == [
        AccountInfo(label="personal", email="bob@proton.me"),
        AccountInfo(label="work", email="alice@proton.me"),
    ]


def test_save_writes_token_file_chmod_600(tmp_config_dir: Path):
    AccountStore().save(
        label="work",
        email="alice@proton.me",
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        bridge_password="pw",
        tls_fingerprint_sha256="a" * 64,
    )
    path = tmp_config_dir / "accounts" / "work.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["email"] == "alice@proton.me"
    assert data["bridge_password"] == "pw"
    assert (path.stat().st_mode & 0o777) == 0o600


def test_load_returns_account_record(tmp_config_dir: Path):
    write_account_file(
        tmp_config_dir / "accounts",
        "work",
        "alice@proton.me",
        bridge_password="my-pw",
        tls_fingerprint="b" * 64,
    )
    rec = AccountStore().load("work")
    assert rec.label == "work"
    assert rec.email == "alice@proton.me"
    assert rec.imap_host == "127.0.0.1"
    assert rec.imap_port == 1143
    assert rec.smtp_host == "127.0.0.1"
    assert rec.smtp_port == 1025
    assert rec.bridge_password == "my-pw"
    assert rec.tls_fingerprint_sha256 == "b" * 64


def test_load_raises_when_label_unknown(tmp_config_dir: Path):
    with pytest.raises(AccountNotConfigured) as excinfo:
        AccountStore().load("nope")
    assert "nope" in str(excinfo.value)


def test_remove_deletes_token_file(tmp_config_dir: Path):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    AccountStore().remove("work")
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_remove_raises_when_label_unknown(tmp_config_dir: Path):
    with pytest.raises(AccountNotConfigured):
        AccountStore().remove("nope")


@pytest.mark.parametrize(
    "evil_label",
    [
        "../escape",
        "../../etc/passwd",
        "subdir/leak",
        "back\\slash",
        ".hidden",
        "..",
        "",
        "has space",
        "a" * 65,
    ],
)
def test_save_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().save(
            label=evil_label,
            email="x@y.com",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )


@pytest.mark.parametrize(
    "evil_label", ["../escape", "subdir/leak", ".hidden", ".."]
)
def test_load_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().load(evil_label)


@pytest.mark.parametrize(
    "evil_label", ["../escape", "subdir/leak", ".hidden", ".."]
)
def test_remove_rejects_malicious_labels(tmp_config_dir: Path, evil_label: str):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().remove(evil_label)


def test_save_does_not_create_files_outside_accounts_dir(tmp_config_dir: Path):
    with pytest.raises(InvalidAccountLabel):
        AccountStore().save(
            label="../../../tmp/leaked",
            email="x@y.com",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )
    assert not (tmp_config_dir.parent / "tmp" / "leaked.json").exists()


def test_save_leaves_no_temp_files_behind(tmp_config_dir: Path):
    AccountStore().save(
        label="work",
        email="a@b.com",
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        bridge_password="pw",
        tls_fingerprint_sha256="c" * 64,
    )
    leftovers = list((tmp_config_dir / "accounts").glob("*.tmp.*"))
    assert leftovers == []


def test_atomic_write_creates_temp_file_with_mode_0600_under_permissive_umask(
    tmp_config_dir: Path,
):
    """Temp file must be created with restrictive perms from the START.

    Forces umask 022 and patches os.chmod to a no-op, so the only way the
    final mode can be 0o600 is if the file was opened with that mode in
    the first place.
    """
    captured_modes: list[int] = []
    real_replace = os.replace

    def probe_replace(src, dst):
        captured_modes.append(os.stat(src).st_mode & 0o777)
        return real_replace(src, dst)

    old_umask = os.umask(0o022)
    try:
        with patch("proton_mcp.accounts.os.chmod"), patch(
            "proton_mcp.accounts.os.replace", side_effect=probe_replace
        ):
            AccountStore().save(
                label="work",
                email="a@b.com",
                imap_host="127.0.0.1",
                imap_port=1143,
                smtp_host="127.0.0.1",
                smtp_port=1025,
                bridge_password="pw",
                tls_fingerprint_sha256="c" * 64,
            )
    finally:
        os.umask(old_umask)

    assert captured_modes == [0o600], (
        f"temp file was created with mode {captured_modes!r} — "
        "secrets exposed during the open->chmod window"
    )


def test_save_preserves_original_on_replace_error(tmp_config_dir: Path):
    """If atomic replace fails mid-way, an existing token must survive."""
    write_account_file(tmp_config_dir / "accounts", "work", "first@proton.me")
    original = (tmp_config_dir / "accounts" / "work.json").read_text()

    with patch(
        "proton_mcp.accounts.os.replace",
        side_effect=OSError("simulated"),
    ), pytest.raises(OSError):
        AccountStore().save(
            label="work",
            email="second@proton.me",
            imap_host="127.0.0.1",
            imap_port=1143,
            smtp_host="127.0.0.1",
            smtp_port=1025,
            bridge_password="pw",
            tls_fingerprint_sha256="c" * 64,
        )

    assert (tmp_config_dir / "accounts" / "work.json").read_text() == original
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_accounts.py -v
```

Expected: `ImportError` — `proton_mcp.accounts` doesn't exist.

- [ ] **Step 3: Implement `accounts.py`**

Create `src/proton_mcp/accounts.py`:

```python
"""Per-account credential storage for the proton-mcp server."""

from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import secrets
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from proton_mcp import config
from proton_mcp.exceptions import AccountNotConfigured, InvalidAccountLabel

# Slug pattern: alphanumerics, hyphen, underscore. 1-64 chars. Anything else
# risks path traversal into ACCOUNTS_DIR via labels like "../../etc/passwd".
_LABEL_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _validate_label(label: str) -> None:
    if not isinstance(label, str) or not _LABEL_RE.fullmatch(label):
        raise InvalidAccountLabel(label)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON to path atomically with mode 0o600 from the start.

    Opening the temp file via os.open with O_CREAT|O_EXCL|O_WRONLY and
    mode 0o600 means the Bridge password is never momentarily readable by
    other local users under a permissive umask. os.replace is atomic on
    POSIX, so a partial write cannot corrupt the live file.
    """
    tmp_path = path.with_name(f"{path.name}.tmp.{secrets.token_hex(8)}")
    try:
        fd = os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as fh:
            json.dump(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp_path, 0o600)  # belt-and-braces
        os.replace(tmp_path, path)
    except Exception:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_path)
        raise


@contextlib.contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Advisory exclusive lock on a sidecar .lock file."""
    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


@dataclass(frozen=True)
class AccountInfo:
    """Lightweight (label, email) row returned by AccountStore.list."""

    label: str
    email: str


@dataclass(frozen=True)
class AccountRecord:
    """Full account record loaded from disk."""

    label: str
    email: str
    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    bridge_password: str
    tls_fingerprint_sha256: str


class AccountStore:
    """Reads, writes, and removes per-account token files."""

    def _path(self, label: str) -> Path:
        _validate_label(label)
        return config.ACCOUNTS_DIR / f"{label}.json"

    def list(self) -> list[AccountInfo]:
        if not config.ACCOUNTS_DIR.exists():
            return []
        out: list[AccountInfo] = []
        for path in sorted(config.ACCOUNTS_DIR.glob("*.json")):
            data = json.loads(path.read_text())
            out.append(AccountInfo(label=data["label"], email=data["email"]))
        return out

    def load(self, label: str) -> AccountRecord:
        path = self._path(label)
        if not path.exists():
            raise AccountNotConfigured(label)
        data = json.loads(path.read_text())
        return AccountRecord(
            label=data["label"],
            email=data["email"],
            imap_host=data["imap_host"],
            imap_port=int(data["imap_port"]),
            smtp_host=data["smtp_host"],
            smtp_port=int(data["smtp_port"]),
            bridge_password=data["bridge_password"],
            tls_fingerprint_sha256=data["tls_fingerprint_sha256"],
        )

    def save(
        self,
        *,
        label: str,
        email: str,
        imap_host: str,
        imap_port: int,
        smtp_host: str,
        smtp_port: int,
        bridge_password: str,
        tls_fingerprint_sha256: str,
    ) -> None:
        config.ACCOUNTS_DIR.mkdir(parents=True, exist_ok=True)
        path = self._path(label)
        with _file_lock(path):
            _atomic_write_json(
                path,
                {
                    "label": label,
                    "email": email,
                    "imap_host": imap_host,
                    "imap_port": imap_port,
                    "smtp_host": smtp_host,
                    "smtp_port": smtp_port,
                    "bridge_password": bridge_password,
                    "tls_fingerprint_sha256": tls_fingerprint_sha256,
                },
            )

    def remove(self, label: str) -> None:
        path = self._path(label)
        if not path.exists():
            raise AccountNotConfigured(label)
        path.unlink()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_accounts.py -v
uv run ruff check .
uv run mypy
```

Expected: all 14 tests pass; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/accounts.py tests/test_accounts.py
git commit -m "feat(accounts): per-label JSON store with atomic writes + path-traversal guard"
```

---

## Phase C — Bridge connection layer

### Task 6: Implement `BridgeSession` (bridge.py)

`bridge.py` is the single boundary between the tool layer and the network. It builds an `IMAPClient` with a TLS-pinned context and an `smtplib.SMTP` with the same context. Connection errors map to `BridgeNotRunning` / `BridgeTLSMismatch` / `BridgeRejectedCredentials`.

**Files:**
- Create: `src/proton_mcp/bridge.py`
- Create: `tests/test_bridge.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_bridge.py`:

```python
from __future__ import annotations

import hashlib
import socket
import ssl
from pathlib import Path
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
    fake_client.login.side_effect = LoginError("bad password")

    with patch("proton_mcp.bridge.IMAPClient", return_value=fake_client):
        with pytest.raises(BridgeRejectedCredentials) as excinfo:
            BridgeSession(_record()).imap()
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
        side_effect=socket.timeout("connect timed out"),
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_bridge.py -v
```

Expected: `ImportError` on `proton_mcp.bridge`.

- [ ] **Step 3: Implement `bridge.py`**

Create `src/proton_mcp/bridge.py`:

```python
"""IMAP + SMTP session helpers with TLS pinning against Proton Bridge."""

from __future__ import annotations

import hashlib
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

    def __init__(self, record: "AccountRecord") -> None:
        self._record = record

    def imap(self) -> IMAPClient:
        """Return a logged-in IMAPClient connected to Bridge.

        Maps network failure → BridgeNotRunning, TLS mismatch →
        BridgeTLSMismatch, auth failure → BridgeRejectedCredentials.
        """
        rec = self._record
        try:
            client = IMAPClient(
                host=rec.imap_host,
                port=rec.imap_port,
                ssl=True,
                ssl_context=pinned_ssl_context(
                    expected_fingerprint=rec.tls_fingerprint_sha256
                ),
                timeout=10,
            )
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            # OSError covers ENETUNREACH, EHOSTUNREACH, etc.
            raise BridgeNotRunning(rec.imap_host, rec.imap_port) from e

        peer_der = client._sock.getpeercert(binary_form=True)
        if fingerprint_sha256(peer_der) != rec.tls_fingerprint_sha256:
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
            smtp = smtplib.SMTP(
                rec.smtp_host, rec.smtp_port, timeout=10
            )
            smtp.ehlo()
            smtp.starttls(
                context=pinned_ssl_context(
                    expected_fingerprint=rec.tls_fingerprint_sha256
                )
            )
            smtp.ehlo()
        except (ConnectionRefusedError, socket.timeout, OSError) as e:
            raise BridgeNotRunning(rec.smtp_host, rec.smtp_port) from e

        peer_der = smtp.sock.getpeercert(binary_form=True)
        if fingerprint_sha256(peer_der) != rec.tls_fingerprint_sha256:
            raise BridgeTLSMismatch(rec.label)

        try:
            smtp.login(rec.email, rec.bridge_password)
        except smtplib.SMTPAuthenticationError as e:
            raise BridgeRejectedCredentials(rec.label) from e
        return smtp


def probe_fingerprint(host: str, port: int, *, timeout: float = 10.0) -> str:
    """One-shot TLS handshake to <host>:<port>, return server cert SHA-256.

    Used by the auth CLI on `add` to display the Bridge fingerprint for
    user TOFU confirmation. STARTTLS is *not* attempted here — Bridge's
    IMAP listener already speaks implicit TLS on the configured port, and
    SMTP is wrapped via STARTTLS but its post-EHLO cert is identical to
    the IMAP cert in practice (same Bridge identity). Probing IMAP keeps
    this helper simple.
    """
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            der = tls.getpeercert(binary_form=True)
    return fingerprint_sha256(der)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_bridge.py -v
uv run ruff check .
uv run mypy
```

Expected: 10 passes; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/bridge.py tests/test_bridge.py
git commit -m "feat(bridge): IMAP+SMTP session helpers with TLS fingerprint pinning"
```

---

## Phase D — Response shaping

### Task 7: Implement `shaping/mail.py` with tests

The shaping module is pure: takes raw `email.message.EmailMessage` (parsed by `email.message_from_bytes`) and `imapclient` FETCH dicts, returns small dicts. No IMAP/SMTP calls.

**Files:**
- Create: `src/proton_mcp/shaping/__init__.py` (empty)
- Create: `src/proton_mcp/shaping/mail.py`
- Create: `tests/shaping/test_mail.py`

- [ ] **Step 1: Create the empty `shaping` package**

`src/proton_mcp/shaping/__init__.py`:

```python
"""Pure helpers that turn raw RFC822 payloads into compact dicts."""
```

- [ ] **Step 2: Write the failing tests**

Create `tests/shaping/test_mail.py`:

```python
from __future__ import annotations

from email.message import EmailMessage

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
    import pytest

    for bad in ["", "INBOX", "INBOX:1", "INBOX:abc:1", "INBOX:1:abc", "::1:2"]:
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
    msg["Date"] = "Mon, 19 May 2026 12:00:00 +0000"
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
    assert summary["date"] == "Mon, 19 May 2026 12:00:00 +0000"
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
    assert full["body_text"] == "PLAIN BODY"


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


def test_shape_attachment_list_skips_inline_parts():
    """Parts without a filename (typical for inline images) aren't attachments."""
    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg.set_content("body")
    msg.add_alternative("<p>hi</p>", subtype="html")
    # inline image — no filename
    msg.add_related(b"PNG", maintype="image", subtype="png")

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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/shaping/test_mail.py -v
```

Expected: `ImportError` on `proton_mcp.shaping.mail`.

- [ ] **Step 4: Implement `shaping/mail.py`**

Create `src/proton_mcp/shaping/mail.py`:

```python
"""Pure shaping helpers: RFC822 → compact dicts, handle codec, folder
metadata extraction."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from email.message import EmailMessage, Message
from typing import Any, Iterable

# IMAP SPECIAL-USE flags → friendly kind. See RFC 6154.
_SPECIAL_USE_FLAGS: dict[bytes, str] = {
    b"\\All": "all",
    b"\\Archive": "archive",
    b"\\Drafts": "drafts",
    b"\\Flagged": "flagged",
    b"\\Junk": "junk",
    b"\\Sent": "sent",
    b"\\Trash": "trash",
    b"\\Important": "important",
}


@dataclass(frozen=True)
class MessageHandle:
    """Composite IMAP identifier: folder:uidvalidity:uid."""

    folder: str
    uidvalidity: int
    uid: int


def encode_handle(handle: MessageHandle) -> str:
    return f"{handle.folder}:{handle.uidvalidity}:{handle.uid}"


def parse_handle(encoded: str) -> MessageHandle:
    """Parse a 'folder:uidvalidity:uid' string into a MessageHandle.

    Folder names can contain ':' in theory but Proton Bridge doesn't use
    them in practice; we split from the right so folder names with one
    colon still parse. Two or more colons in the folder would break this;
    callers should treat that as malformed input.
    """
    parts = encoded.rsplit(":", 2)
    if len(parts) != 3 or not parts[0]:
        raise ValueError(f"malformed message handle: {encoded!r}")
    folder, uv_str, uid_str = parts
    try:
        uidvalidity = int(uv_str)
        uid = int(uid_str)
    except ValueError as e:
        raise ValueError(f"malformed message handle: {encoded!r}") from e
    return MessageHandle(folder=folder, uidvalidity=uidvalidity, uid=uid)


def shape_folder(
    *,
    flags: Iterable[bytes],
    delimiter: bytes,
    name: bytes,
    message_count: int,
    unseen_count: int,
) -> dict[str, Any]:
    """Shape an IMAP LIST + STATUS result into a folder dict."""
    flag_set = set(flags)
    kind: str | None = None
    for flag, mapped in _SPECIAL_USE_FLAGS.items():
        if flag in flag_set:
            kind = mapped
            break
    name_str = name.decode("utf-8", errors="replace")
    return {
        "name": name_str,
        "path": name_str,
        "is_special": kind is not None,
        "special_kind": kind,
        "message_count": message_count,
        "unseen_count": unseen_count,
    }


def _flags_to_strings(flags: Iterable[bytes]) -> list[str]:
    return [f.decode("ascii", errors="replace") for f in flags]


def _snippet(msg: Message, *, max_chars: int = 200) -> str:
    body = _extract_text_body(msg)
    cleaned = re.sub(r"\s+", " ", body).strip()
    return cleaned[:max_chars]


def shape_message_summary(
    msg: Message,
    *,
    handle: str,
    folder: str,
    flags: Iterable[bytes],
) -> dict[str, Any]:
    """Compact dict for search results."""
    return {
        "handle": handle,
        "message_id": msg.get("Message-ID", ""),
        "from": msg.get("From", ""),
        "to": msg.get("To", ""),
        "cc": msg.get("Cc", ""),
        "subject": msg.get("Subject", ""),
        "date": msg.get("Date", ""),
        "folder": folder,
        "flags": _flags_to_strings(flags),
        "snippet": _snippet(msg),
    }


def shape_message_full(
    msg: Message,
    *,
    handle: str,
    folder: str,
    flags: Iterable[bytes],
) -> dict[str, Any]:
    """Summary + body_text + attachments metadata."""
    summary = shape_message_summary(
        msg, handle=handle, folder=folder, flags=flags
    )
    return {
        **summary,
        "body_text": _extract_text_body(msg),
        "attachments": shape_attachment_list(msg),
    }


def shape_attachment_list(msg: Message) -> list[dict[str, Any]]:
    """List attachment metadata. attachment_id is a stable hash of the
    filename + content-id + index so callers can re-fetch via
    mail_get_attachment without us needing an actual ID from the IMAP
    server (IMAP exposes parts by BODY[N]; we resolve N at fetch time)."""
    out: list[dict[str, Any]] = []
    index = 0
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True) or b""
        cid = part.get("Content-ID", "")
        # Stable per-message attachment id: index is the
        # message-walk position of this part (1-based at the leaf level).
        # We hash the position+filename+CID together so re-fetches can
        # validate the caller is asking for the part we shaped.
        index += 1
        attachment_id = hashlib.sha256(
            f"{index}:{filename}:{cid}".encode()
        ).hexdigest()[:16]
        out.append(
            {
                "attachment_id": attachment_id,
                "filename": filename,
                "mime": part.get_content_type(),
                "size": len(payload),
                "_part_index": index,
            }
        )
    return out


def _extract_text_body(msg: Message) -> str:
    """Prefer text/plain; fall back to stripped text/html."""
    # text/plain anywhere in the tree
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_content_type() == "text/plain":
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            return payload.decode(charset, errors="replace")
    # fall back to text/html with naive tag-stripping
    for part in msg.walk():
        if part.is_multipart():
            continue
        if part.get_content_type() == "text/html":
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            html = payload.decode(charset, errors="replace")
            no_tags = re.sub(r"<[^>]+>", "", html)
            return re.sub(r"\s+", " ", no_tags).strip()
    return ""


def truncate_body(body: str, *, cap: int) -> str:
    raw = body.encode("utf-8")
    if len(raw) <= cap:
        return body
    cut = raw[:cap].decode("utf-8", errors="replace")
    return f"{cut}\n\n[...truncated: {len(raw)} bytes total, showing first {cap}]"
```

Note: `EmailMessage` is imported in tests for its convenient builder API. Tests use it; the shape functions accept the broader `Message` type so they also accept the result of `email.message_from_bytes`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/shaping/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: 12 passes; lint and mypy clean.

- [ ] **Step 6: Commit**

```bash
git add src/proton_mcp/shaping/__init__.py src/proton_mcp/shaping/mail.py tests/shaping/test_mail.py
git commit -m "feat(shaping): RFC822 → compact dicts, handle codec, folder metadata"
```

---

## Phase E — Tools

The tool module is built up in five tasks (8–12), one slice of the tool surface per task. Each slice adds tests against a mocked `BridgeSession` and `imapclient`. The `conftest` is extended once at the top of this phase with a shared `mock_bridge` fixture.

### Task 8: Add the `mock_bridge` fixture and implement `list_accounts` + `mail_list_folders`

**Files:**
- Modify: `tests/conftest.py`
- Create: `src/proton_mcp/tools/__init__.py` (empty)
- Create: `src/proton_mcp/tools/mail.py`
- Create: `tests/tools/test_mail.py`

- [ ] **Step 1: Add the `mock_bridge` fixture to `tests/conftest.py`**

Append to `tests/conftest.py`:

```python
from unittest.mock import MagicMock


@pytest.fixture
def mock_bridge(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Patch BridgeSession used by proton_mcp.tools.mail.

    Returns a dict with:
        "imap":  MagicMock standing in for IMAPClient
        "smtp":  MagicMock standing in for smtplib.SMTP
        "calls": list of (label, "imap"|"smtp") to assert routing
    """
    import importlib

    imap = MagicMock(name="IMAPClient")
    smtp = MagicMock(name="SMTP")
    calls: list[tuple[str, str]] = []

    class FakeSession:
        def __init__(self, record):
            self._record = record

        def imap(self):
            calls.append((self._record.label, "imap"))
            return imap

        def smtp(self):
            calls.append((self._record.label, "smtp"))
            return smtp

    try:
        mod = importlib.import_module("proton_mcp.tools.mail")
    except ImportError:
        return {"imap": imap, "smtp": smtp, "calls": calls, "FakeSession": FakeSession}
    monkeypatch.setattr(mod, "BridgeSession", FakeSession)
    return {"imap": imap, "smtp": smtp, "calls": calls, "FakeSession": FakeSession}
```

- [ ] **Step 2: Create empty `tools/__init__.py`**

`src/proton_mcp/tools/__init__.py`:

```python
"""MCP tool implementations."""
```

- [ ] **Step 3: Write failing tests for `list_accounts` and `mail_list_folders`**

Create `tests/tools/test_mail.py`:

```python
from __future__ import annotations

from pathlib import Path

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
    # STATUS calls return EXISTS/UNSEEN per folder
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
```

- [ ] **Step 4: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_mail.py -v
```

Expected: ImportError on `proton_mcp.tools.mail`.

- [ ] **Step 5: Implement `tools/mail.py` initial slice**

Create `src/proton_mcp/tools/mail.py`:

```python
"""MCP tool implementations for Proton Mail via Bridge."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from proton_mcp.accounts import AccountStore
from proton_mcp.bridge import BridgeSession
from proton_mcp.shaping.mail import shape_folder

_store = AccountStore()


def _session(account: str) -> BridgeSession:
    return BridgeSession(_store.load(account))


def list_accounts() -> list[dict[str, str]]:
    return [asdict(a) for a in _store.list()]


def mail_list_folders(account: str) -> list[dict[str, Any]]:
    session = _session(account)
    imap = session.imap()
    try:
        listed = imap.list_folders()
        out: list[dict[str, Any]] = []
        for flags, delimiter, name in listed:
            name_bytes = name.encode("utf-8") if isinstance(name, str) else name
            status = imap.folder_status(name, [b"MESSAGES", b"UNSEEN"])
            out.append(
                shape_folder(
                    flags=flags,
                    delimiter=delimiter,
                    name=name_bytes,
                    message_count=int(status.get(b"MESSAGES", 0)),
                    unseen_count=int(status.get(b"UNSEEN", 0)),
                )
            )
        return out
    finally:
        try:
            imap.logout()
        except Exception:
            pass
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: 2 passes; lint and mypy clean.

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py src/proton_mcp/tools/__init__.py src/proton_mcp/tools/mail.py tests/tools/test_mail.py
git commit -m "feat(tools): list_accounts + mail_list_folders"
```

---

### Task 9: Implement `mail_search`

**Files:**
- Modify: `src/proton_mcp/tools/mail.py`
- Modify: `tests/tools/test_mail.py`

- [ ] **Step 1: Append failing tests to `tests/tools/test_mail.py`**

```python
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
                b"Date: Mon, 19 May 2026 12:00:00 +0000\r\n"
                b"Message-ID: <42@proton>\r\n\r\n"
            ),
        },
        43: {
            b"FLAGS": (),
            b"RFC822.HEADER": (
                b"From: e@f\r\nTo: g@h\r\nSubject: world\r\n"
                b"Date: Mon, 19 May 2026 12:01:00 +0000\r\n"
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
    assert hits[0]["handle"] == "INBOX:1700000001:42"
    assert hits[0]["subject"] == "hello"
    assert hits[1]["handle"] == "INBOX:1700000001:43"

    # Verify the IMAP SEARCH criteria built from the query dict.
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
    imap.search.return_value = [10, 11, 12, 13, 14]  # 5 hits
    imap.fetch.return_value = {
        uid: {
            b"FLAGS": (),
            b"RFC822.HEADER": (
                b"From: x@y\r\nTo: z@y\r\nSubject: s\r\n"
                b"Date: \r\nMessage-ID: <" + str(uid).encode() + b"@p>\r\n\r\n"
            ),
        }
        for uid in [12, 13, 14]  # only newest 3 fetched
    }

    hits = mail_tools.mail_search(
        account="work",
        query={},
        folder="INBOX",
        max_results=3,
    )

    # Search returns oldest-first; we want newest-first, capped at max_results.
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_mail.py -v -k search
```

Expected: `AttributeError: module 'proton_mcp.tools.mail' has no attribute 'mail_search'`.

- [ ] **Step 3: Add `mail_search` to `tools/mail.py`**

Append to `src/proton_mcp/tools/mail.py`:

```python
import datetime as dt
from email import message_from_bytes
from email.message import Message

from proton_mcp.shaping.mail import (
    MessageHandle,
    encode_handle,
    shape_message_summary,
)


_DATE_FIELDS = {"since", "before"}
_TEXT_FIELDS = {
    "from": "FROM",
    "to": "TO",
    "cc": "CC",
    "subject": "SUBJECT",
    "text": "TEXT",
}
_FLAG_FIELDS = {
    "seen": ("SEEN", "UNSEEN"),
    "flagged": ("FLAGGED", "UNFLAGGED"),
    "answered": ("ANSWERED", "UNANSWERED"),
}


def _build_search_criteria(query: dict[str, Any]) -> list[Any]:
    """Translate {from, subject, since, seen, ...} into imapclient SEARCH args.

    imapclient accepts criteria as a flat list of strings/values where text
    fields take a SEARCH keyword followed by their value. Date fields use
    a date string like "19-May-2026". Boolean flag fields map to two
    keywords (SEEN vs UNSEEN).
    """
    if not query:
        return ["ALL"]
    criteria: list[Any] = []
    for k, v in query.items():
        if k in _TEXT_FIELDS and v:
            criteria.extend([_TEXT_FIELDS[k], str(v)])
        elif k in _DATE_FIELDS and v:
            parsed = dt.date.fromisoformat(str(v))
            criteria.extend([k.upper(), parsed.strftime("%d-%b-%Y")])
        elif k in _FLAG_FIELDS:
            on, off = _FLAG_FIELDS[k]
            criteria.append(on if v else off)
    if not criteria:
        return ["ALL"]
    return criteria


def mail_search(
    account: str,
    query: dict[str, Any],
    folder: str = "INBOX",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    session = _session(account)
    imap = session.imap()
    try:
        select_info = imap.select_folder(folder, readonly=True)
        uidvalidity = int(select_info[b"UIDVALIDITY"])
        criteria = _build_search_criteria(query)
        uids = imap.search(criteria)
        # Newest-first by UID, capped at max_results.
        uids_sorted = sorted(uids, reverse=True)[:max_results]
        if not uids_sorted:
            return []
        fetched = imap.fetch(uids_sorted, [b"FLAGS", b"RFC822.HEADER"])

        out: list[dict[str, Any]] = []
        for uid in uids_sorted:
            data = fetched.get(uid)
            if data is None:
                continue
            header_bytes = data.get(b"RFC822.HEADER", b"")
            msg: Message = message_from_bytes(header_bytes)
            handle = encode_handle(
                MessageHandle(folder=folder, uidvalidity=uidvalidity, uid=uid)
            )
            out.append(
                shape_message_summary(
                    msg,
                    handle=handle,
                    folder=folder,
                    flags=data.get(b"FLAGS", ()),
                )
            )
        return out
    finally:
        try:
            imap.logout()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: all 5 tests pass; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/tools/mail.py tests/tools/test_mail.py
git commit -m "feat(tools): mail_search with structured query → IMAP criteria"
```

---

### Task 10: Implement `mail_get_message` and `mail_get_attachment`

**Files:**
- Modify: `src/proton_mcp/tools/mail.py`
- Modify: `tests/tools/test_mail.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/tools/test_mail.py`:

```python
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
        b"Date: Mon, 19 May 2026 12:00:00 +0000\r\n"
        b"Message-ID: <42@proton>\r\n"
        b"MIME-Version: 1.0\r\n"
        b"Content-Type: text/plain; charset=utf-8\r\n"
        b"\r\n"
        b"PLAIN BODY"
    )
    imap.fetch.return_value = {42: {b"FLAGS": (b"\\Seen",), b"RFC822": raw}}

    msg = mail_tools.mail_get_message(
        account="work", handle="INBOX:1700000001:42"
    )
    assert msg["handle"] == "INBOX:1700000001:42"
    assert msg["subject"] == "hello"
    assert msg["body_text"] == "PLAIN BODY"
    assert msg["attachments"] == []


def test_mail_get_message_stale_handle_raises(
    tmp_config_dir: Path, mock_bridge: dict
):
    import pytest

    from proton_mcp.exceptions import MessageHandleStale

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    # Folder's current UIDVALIDITY is different from the handle's.
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
    imap.fetch.return_value = {1: {b"FLAGS": (), b"RFC822": raw}}

    msg = mail_tools.mail_get_message(account="work", handle="INBOX:1:1")
    assert "[...truncated:" in msg["body_text"]
    assert "5000 bytes total" in msg["body_text"]


def test_mail_get_attachment_returns_base64_content(
    tmp_config_dir: Path, mock_bridge: dict
):
    import base64

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}

    # Build a multipart email with one PDF attachment via the email module.
    from email.message import EmailMessage

    msg = EmailMessage()
    msg["From"] = "a@b"
    msg["To"] = "c@d"
    msg["Subject"] = "s"
    msg["Date"] = "Mon, 19 May 2026 12:00:00 +0000"
    msg["Message-ID"] = "<1@p>"
    msg.set_content("body")
    msg.add_attachment(
        b"PDFCONTENT", maintype="application", subtype="pdf", filename="invoice.pdf"
    )
    raw_bytes = bytes(msg)

    # First fetch resolves the attachment metadata; second fetch pulls bytes.
    imap.fetch.return_value = {1: {b"FLAGS": (), b"RFC822": raw_bytes}}

    # Discover the attachment_id from get_message first.
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
    import pytest

    from proton_mcp import config as cfg
    from proton_mcp.exceptions import AttachmentTooLarge

    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    monkeypatch.setattr(cfg, "MAX_ATTACHMENT_BYTES", 5)

    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}

    from email.message import EmailMessage

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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_mail.py -v -k "get_message or get_attachment"
```

Expected: `AttributeError` on `mail_get_message` / `mail_get_attachment`.

- [ ] **Step 3: Add `mail_get_message` and `mail_get_attachment` to `tools/mail.py`**

Append to `src/proton_mcp/tools/mail.py`:

```python
import base64

from proton_mcp import config
from proton_mcp.exceptions import AttachmentTooLarge, MessageHandleStale
from proton_mcp.shaping.mail import (
    parse_handle,
    shape_attachment_list,
    shape_message_full,
    truncate_body,
)


def _fetch_full_message(imap, handle_str: str) -> tuple[Message, dict[str, Any]]:
    """Open the folder, validate UIDVALIDITY, return (parsed email, fetch_data)."""
    handle = parse_handle(handle_str)
    select_info = imap.select_folder(handle.folder, readonly=True)
    if int(select_info[b"UIDVALIDITY"]) != handle.uidvalidity:
        raise MessageHandleStale(handle_str)
    fetched = imap.fetch([handle.uid], [b"FLAGS", b"RFC822"])
    data = fetched.get(handle.uid)
    if data is None:
        raise MessageHandleStale(handle_str)
    msg = message_from_bytes(data[b"RFC822"])
    return msg, data


def mail_get_message(account: str, handle: str) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        msg, data = _fetch_full_message(imap, handle)
        h = parse_handle(handle)
        shaped = shape_message_full(
            msg, handle=handle, folder=h.folder, flags=data.get(b"FLAGS", ())
        )
        shaped["body_text"] = truncate_body(
            shaped["body_text"], cap=config.MAX_MAIL_BODY_BYTES
        )
        # Drop the internal _part_index from the public payload.
        for att in shaped["attachments"]:
            att.pop("_part_index", None)
        return shaped
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def mail_get_attachment(
    account: str, handle: str, attachment_id: str
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        msg, _data = _fetch_full_message(imap, handle)
        atts = shape_attachment_list(msg)
        match = next(
            (a for a in atts if a["attachment_id"] == attachment_id), None
        )
        if match is None:
            raise ValueError(
                f"attachment {attachment_id!r} not found on message {handle!r}"
            )
        if match["size"] > config.MAX_ATTACHMENT_BYTES:
            raise AttachmentTooLarge(
                size=match["size"], cap=config.MAX_ATTACHMENT_BYTES
            )
        # Re-walk to pull the actual bytes (shape_attachment_list discarded them).
        target_index = match["_part_index"]
        index = 0
        payload = b""
        for part in msg.walk():
            if part.is_multipart():
                continue
            if not part.get_filename():
                continue
            index += 1
            if index == target_index:
                payload = part.get_payload(decode=True) or b""
                break
        return {
            "filename": match["filename"],
            "mime": match["mime"],
            "size": match["size"],
            "content_b64": base64.b64encode(payload).decode("ascii"),
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: all 10 tests pass; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/tools/mail.py tests/tools/test_mail.py
git commit -m "feat(tools): mail_get_message + mail_get_attachment"
```

---

### Task 11: Implement `mail_send` and `mail_create_draft`

**Files:**
- Modify: `src/proton_mcp/tools/mail.py`
- Modify: `tests/tools/test_mail.py`

- [ ] **Step 1: Append failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_mail.py -v -k "send or draft"
```

Expected: AttributeError on `mail_send` / `mail_create_draft`.

- [ ] **Step 3: Implement `mail_send` and `mail_create_draft`**

Append to `src/proton_mcp/tools/mail.py`:

```python
from email.message import EmailMessage
from email.utils import make_msgid

from proton_mcp.exceptions import OutboundTooLarge


def _build_outbound(
    *,
    sender: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None,
    bcc: str | None,
    html: bool,
    in_reply_to: str | None,
    attachments: list[dict[str, Any]] | None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    if cc:
        msg["Cc"] = cc
    if bcc:
        msg["Bcc"] = bcc
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
        msg["References"] = in_reply_to

    if html:
        msg.set_content("This message contains HTML — please use an HTML client.")
        msg.add_alternative(body, subtype="html")
    else:
        msg.set_content(body)

    for att in attachments or []:
        raw = base64.b64decode(att["content_b64"])
        maintype, _, subtype = att["mime"].partition("/")
        msg.add_attachment(
            raw,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=att["filename"],
        )

    total = len(bytes(msg))
    if total > config.MAX_OUTBOUND_BYTES:
        raise OutboundTooLarge(size=total, cap=config.MAX_OUTBOUND_BYTES)
    return msg


def mail_send(
    account: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    rec = _store.load(account)
    msg = _build_outbound(
        sender=rec.email,
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        html=html,
        in_reply_to=in_reply_to,
        attachments=attachments,
    )
    smtp = BridgeSession(rec).smtp()
    try:
        smtp.send_message(msg)
    finally:
        try:
            smtp.quit()
        except Exception:
            pass
    return {"message_id": msg["Message-ID"]}


def _find_special_folder(imap, kind: str) -> str:
    """Resolve a SPECIAL-USE folder (\\Drafts, \\Trash, ...) to its name."""
    flag = f"\\{kind.capitalize()}".encode()
    for flags, _delim, name in imap.list_folders():
        if flag in flags:
            return name if isinstance(name, str) else name.decode("utf-8")
    raise ValueError(f"no folder marked as {kind!r} on this account")


def mail_create_draft(
    account: str,
    to: str,
    subject: str,
    body: str,
    cc: str | None = None,
    bcc: str | None = None,
    html: bool = False,
    in_reply_to: str | None = None,
    attachments: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    rec = _store.load(account)
    msg = _build_outbound(
        sender=rec.email,
        to=to,
        subject=subject,
        body=body,
        cc=cc,
        bcc=bcc,
        html=html,
        in_reply_to=in_reply_to,
        attachments=attachments,
    )
    session = BridgeSession(rec)
    imap = session.imap()
    try:
        drafts = _find_special_folder(imap, "drafts")
        imap.append(drafts, bytes(msg), [b"\\Draft"], None)
    finally:
        try:
            imap.logout()
        except Exception:
            pass
    return {"message_id": msg["Message-ID"]}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: all 16 tests pass; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/tools/mail.py tests/tools/test_mail.py
git commit -m "feat(tools): mail_send + mail_create_draft with size cap and threading"
```

---

### Task 12: Implement `mail_modify_flags`, `mail_move_message`, and `mail_trash`

**Files:**
- Modify: `src/proton_mcp/tools/mail.py`
- Modify: `tests/tools/test_mail.py`

- [ ] **Step 1: Append failing tests**

```python
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
    assert "\\Seen" not in result["flags"]


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
    imap.has_capability.return_value = True
    imap.move = MagicMock()

    result = mail_tools.mail_move_message(
        account="work", handle="INBOX:1:42", dest_folder="Archive"
    )

    imap.move.assert_called_once_with([42], "Archive")
    assert result["moved_to"] == "Archive"


def test_mail_move_message_falls_back_to_copy_when_no_move_capability(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.return_value = False

    mail_tools.mail_move_message(
        account="work", handle="INBOX:1:42", dest_folder="Archive"
    )

    imap.copy.assert_called_once_with([42], "Archive")
    imap.add_flags.assert_called_once_with([42], [b"\\Deleted"])
    imap.expunge.assert_called_once()


def test_mail_trash_moves_to_special_trash_folder(
    tmp_config_dir: Path, mock_bridge: dict
):
    write_account_file(tmp_config_dir / "accounts", "work", "a@proton.me")
    imap = mock_bridge["imap"]
    imap.select_folder.return_value = {b"UIDVALIDITY": 1}
    imap.has_capability.return_value = True
    imap.list_folders.return_value = [
        ((b"\\HasNoChildren",), b"/", "INBOX"),
        ((b"\\Trash", b"\\HasNoChildren"), b"/", "Trash"),
    ]

    result = mail_tools.mail_trash(account="work", handle="INBOX:1:42")
    imap.move.assert_called_once_with([42], "Trash")
    assert result["moved_to"] == "Trash"
```

Add the necessary import to the top of the test file (the `MagicMock` symbol is new for this slice):

```python
from unittest.mock import MagicMock
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/tools/test_mail.py -v -k "modify_flags or move or trash"
```

Expected: AttributeError on `mail_modify_flags` / `mail_move_message` / `mail_trash`.

- [ ] **Step 3: Implement the three tools**

Append to `src/proton_mcp/tools/mail.py`:

```python
def _open_for_write(imap, handle_str: str) -> int:
    """select_folder (writeable) and validate UIDVALIDITY; return uid."""
    handle = parse_handle(handle_str)
    select_info = imap.select_folder(handle.folder, readonly=False)
    if int(select_info[b"UIDVALIDITY"]) != handle.uidvalidity:
        raise MessageHandleStale(handle_str)
    return handle.uid


def mail_modify_flags(
    account: str,
    handle: str,
    add_flags: list[str] | None = None,
    remove_flags: list[str] | None = None,
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        if add_flags:
            imap.add_flags([uid], [f.encode("ascii") for f in add_flags])
        if remove_flags:
            imap.remove_flags([uid], [f.encode("ascii") for f in remove_flags])
        current = imap.get_flags([uid]).get(uid, ())
        return {
            "handle": handle,
            "flags": [f.decode("ascii", errors="replace") for f in current],
        }
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _move_uid(imap, uid: int, dest_folder: str) -> None:
    """IMAP MOVE if advertised, else COPY + \\Deleted + EXPUNGE."""
    if imap.has_capability("MOVE"):
        imap.move([uid], dest_folder)
    else:
        imap.copy([uid], dest_folder)
        imap.add_flags([uid], [b"\\Deleted"])
        imap.expunge()


def mail_move_message(
    account: str, handle: str, dest_folder: str
) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        _move_uid(imap, uid, dest_folder)
        return {"handle": handle, "moved_to": dest_folder}
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def mail_trash(account: str, handle: str) -> dict[str, Any]:
    session = _session(account)
    imap = session.imap()
    try:
        uid = _open_for_write(imap, handle)
        trash = _find_special_folder(imap, "trash")
        _move_uid(imap, uid, trash)
        return {"handle": handle, "moved_to": trash}
    finally:
        try:
            imap.logout()
        except Exception:
            pass
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/tools/test_mail.py -v
uv run ruff check .
uv run mypy
```

Expected: all 21 tests pass; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/tools/mail.py tests/tools/test_mail.py
git commit -m "feat(tools): mail_modify_flags, mail_move_message, mail_trash"
```

---

## Phase F — MCP server entrypoint

### Task 13: Implement `server.py` with TOOL_REGISTRY

**Files:**
- Create: `src/proton_mcp/server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for the server registry and error funnel**

Create `tests/test_server.py`:

```python
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from proton_mcp.exceptions import AccountNotConfigured, BridgeNotRunning
from proton_mcp.server import TOOL_REGISTRY, _invoke_tool, build_app


def test_tool_registry_contains_expected_names():
    names = {t["name"] for t in TOOL_REGISTRY}
    expected = {
        "list_accounts",
        "mail_list_folders",
        "mail_search",
        "mail_get_message",
        "mail_get_attachment",
        "mail_send",
        "mail_create_draft",
        "mail_modify_flags",
        "mail_move_message",
        "mail_trash",
    }
    assert names == expected


def test_every_tool_has_inputschema():
    for tool in TOOL_REGISTRY:
        schema = tool["schema"]
        assert schema["type"] == "object"
        assert "properties" in schema


def test_every_operational_tool_requires_account():
    for tool in TOOL_REGISTRY:
        if tool["name"] == "list_accounts":
            continue
        required = tool["schema"].get("required", [])
        assert "account" in required, f"{tool['name']} missing account in required"


def test_invoke_tool_unknown_returns_error_text():
    assert _invoke_tool("not_a_tool", {}) == "error: unknown tool 'not_a_tool'"


def test_invoke_tool_returns_json_string_on_success(tmp_config_dir: Path):
    """list_accounts has no external deps; verify the happy path serializes."""
    out = _invoke_tool("list_accounts", {})
    assert out == json.dumps([])


def test_invoke_tool_account_not_configured_surfaces_as_error_string():
    with patch(
        "proton_mcp.server._dispatch",
        side_effect=AccountNotConfigured("work"),
    ):
        out = _invoke_tool("mail_search", {"account": "work", "query": {}})
    assert out.startswith("error:")
    assert "work" in out
    assert "proton-mcp-auth add work" in out


def test_invoke_tool_bridge_not_running_surfaces_as_error_string():
    with patch(
        "proton_mcp.server._dispatch",
        side_effect=BridgeNotRunning("127.0.0.1", 1143),
    ):
        out = _invoke_tool("mail_list_folders", {"account": "work"})
    assert out.startswith("error:")
    assert "127.0.0.1:1143" in out


def test_invoke_tool_bad_arguments_surfaces_as_error_string():
    with patch(
        "proton_mcp.server._dispatch",
        side_effect=TypeError("unexpected keyword argument 'foo'"),
    ):
        out = _invoke_tool("mail_search", {"foo": "bar"})
    assert out.startswith("error: invalid arguments")


def test_invoke_tool_unexpected_exception_surfaces_as_internal_error():
    with patch(
        "proton_mcp.server._dispatch",
        side_effect=RuntimeError("boom"),
    ):
        out = _invoke_tool("mail_search", {"account": "work", "query": {}})
    assert out.startswith("error: internal error")
    assert "RuntimeError" in out
    assert "boom" in out


def test_build_app_registers_all_tools():
    app = build_app()

    async def collect_tools():
        # The decorator registers an async handler that returns the tool list.
        list_tools_handler = app.request_handlers.get(
            __import__("mcp.types").types.ListToolsRequest
        )
        if list_tools_handler is None:
            return []
        result = await list_tools_handler(
            __import__("mcp.types").types.ListToolsRequest(method="tools/list")
        )
        return result.root.tools

    tools = asyncio.run(collect_tools())
    assert {t.name for t in tools} == {t["name"] for t in TOOL_REGISTRY}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_server.py -v
```

Expected: `ImportError` on `proton_mcp.server`.

- [ ] **Step 3: Implement `server.py`**

Create `src/proton_mcp/server.py`:

```python
"""MCP server entrypoint: register tools, run over stdio."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from proton_mcp.exceptions import ProtonMcpError
from proton_mcp.tools import mail as mail_tools


TOOL_REGISTRY: list[dict[str, Any]] = [
    {
        "name": "list_accounts",
        "description": "List configured Proton accounts (label + email).",
        "schema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "handler": lambda args: mail_tools.list_accounts(),
    },
    {
        "name": "mail_list_folders",
        "description": "List IMAP folders on the account, including special-use kinds.",
        "schema": {
            "type": "object",
            "properties": {"account": {"type": "string"}},
            "required": ["account"],
        },
        "handler": lambda args: mail_tools.mail_list_folders(**args),
    },
    {
        "name": "mail_search",
        "description": (
            "Search a folder with a structured query. "
            "query keys: from, to, cc, subject, text, since, before, seen, flagged, answered."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "query": {"type": "object"},
                "folder": {"type": "string", "default": "INBOX"},
                "max_results": {"type": "integer", "default": 20},
            },
            "required": ["account", "query"],
        },
        "handler": lambda args: mail_tools.mail_search(**args),
    },
    {
        "name": "mail_get_message",
        "description": (
            "Fetch a Proton message in full (headers, text body, attachment "
            "metadata). Body capped per MAX_MAIL_BODY_BYTES."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "handle": {"type": "string"},
            },
            "required": ["account", "handle"],
        },
        "handler": lambda args: mail_tools.mail_get_message(**args),
    },
    {
        "name": "mail_get_attachment",
        "description": "Download one attachment as base64. Capped per MAX_ATTACHMENT_BYTES.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "handle": {"type": "string"},
                "attachment_id": {"type": "string"},
            },
            "required": ["account", "handle", "attachment_id"],
        },
        "handler": lambda args: mail_tools.mail_get_attachment(**args),
    },
    {
        "name": "mail_send",
        "description": (
            "Send a Proton mail via Bridge SMTP. "
            "attachments: [{filename, mime, content_b64}]."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
                "html": {"type": "boolean", "default": False},
                "in_reply_to": {"type": "string"},
                "attachments": {"type": "array"},
            },
            "required": ["account", "to", "subject", "body"],
        },
        "handler": lambda args: mail_tools.mail_send(**args),
    },
    {
        "name": "mail_create_draft",
        "description": "Create a draft in the account's Drafts folder.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"type": "string"},
                "bcc": {"type": "string"},
                "html": {"type": "boolean", "default": False},
                "in_reply_to": {"type": "string"},
                "attachments": {"type": "array"},
            },
            "required": ["account", "to", "subject", "body"],
        },
        "handler": lambda args: mail_tools.mail_create_draft(**args),
    },
    {
        "name": "mail_modify_flags",
        "description": (
            "Add or remove IMAP flags (\\Seen, \\Flagged, \\Answered, \\Draft)."
        ),
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "handle": {"type": "string"},
                "add_flags": {"type": "array", "items": {"type": "string"}},
                "remove_flags": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["account", "handle"],
        },
        "handler": lambda args: mail_tools.mail_modify_flags(**args),
    },
    {
        "name": "mail_move_message",
        "description": "Move a message into another folder (IMAP MOVE or COPY+EXPUNGE).",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "handle": {"type": "string"},
                "dest_folder": {"type": "string"},
            },
            "required": ["account", "handle", "dest_folder"],
        },
        "handler": lambda args: mail_tools.mail_move_message(**args),
    },
    {
        "name": "mail_trash",
        "description": "Move a message to the account's Trash folder.",
        "schema": {
            "type": "object",
            "properties": {
                "account": {"type": "string"},
                "handle": {"type": "string"},
            },
            "required": ["account", "handle"],
        },
        "handler": lambda args: mail_tools.mail_trash(**args),
    },
]


def _dispatch(name: str, arguments: dict[str, Any]) -> Any:
    """Resolve the registry entry and call its handler. Indirected so tests
    can patch one function for the whole error-funnel surface."""
    entry = next((t for t in TOOL_REGISTRY if t["name"] == name), None)
    if entry is None:
        raise KeyError(name)
    return entry["handler"](arguments or {})


def _invoke_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run a tool by name and return JSON output or an error: text payload.

    Every plausible operational failure converts to a stable "error: ..."
    string so the MCP transport never sees a Python exception. Categories:

    - ProtonMcpError: account / bridge / size errors, message verbatim.
    - ValueError / TypeError / KeyError: malformed arguments.
    - Anything else: rendered with class name + message so a bug is at
      least diagnosable from the client side without a full traceback.
    """
    try:
        result = _dispatch(name, arguments)
    except KeyError:
        return f"error: unknown tool {name!r}"
    except ProtonMcpError as e:
        return f"error: {e}"
    except (ValueError, TypeError) as e:
        return f"error: invalid arguments: {type(e).__name__}: {e}"
    except Exception as e:
        return f"error: internal error: {type(e).__name__}: {e}"
    return json.dumps(result, default=str)


def build_app() -> Server:
    app: Server = Server("proton-mcp")

    @app.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=t["name"],
                description=t["description"],
                inputSchema=t["schema"],
            )
            for t in TOOL_REGISTRY
        ]

    @app.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[TextContent]:
        return [TextContent(type="text", text=_invoke_tool(name, arguments))]

    return app


def main() -> None:
    async def runner() -> None:
        async with stdio_server() as (read, write):
            app = build_app()
            await app.run(read, write, app.create_initialization_options())

    asyncio.run(runner())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_server.py -v
uv run pytest -v
uv run ruff check .
uv run mypy
```

Expected: all server tests pass; full suite is green; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/server.py tests/test_server.py
git commit -m "feat(server): TOOL_REGISTRY with stable error-funnel"
```

---

## Phase G — Auth CLI

### Task 14: Implement `auth_cli.py` with `add`/`list`/`remove`/`test`

The CLI is non-interactive in tests (`getpass`/`input` are monkey-patched). It validates credentials against Bridge before persisting on `add`.

**Files:**
- Create: `src/proton_mcp/auth_cli.py`
- Create: `tests/test_auth_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_auth_cli.py`:

```python
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proton_mcp.auth_cli import main
from tests.conftest import write_account_file


def _stub_inputs(monkeypatch: pytest.MonkeyPatch, answers: list[str]) -> None:
    answers_iter = iter(answers)
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(answers_iter))
    monkeypatch.setattr("getpass.getpass", lambda *a, **kw: next(answers_iter))


def test_add_persists_account_after_validation_succeeds(
    tmp_config_dir: Path, monkeypatch, capsys
):
    # Order matches the CLI prompt sequence: email, password (getpass),
    # imap_host, imap_port, smtp_host, smtp_port, fingerprint confirm "y"
    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "bridge-pw",  # getpass
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "y",
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )
    # Stub the validating bridge session so we don't open real sockets.
    fake_session = MagicMock()
    fake_session.imap.return_value = MagicMock()
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["add", "work"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Saved account 'work'" in out
    data = json.loads(
        (tmp_config_dir / "accounts" / "work.json").read_text()
    )
    assert data["bridge_password"] == "bridge-pw"
    assert data["tls_fingerprint_sha256"] == "f" * 64


def test_add_aborts_if_user_declines_fingerprint(
    tmp_config_dir: Path, monkeypatch, capsys
):
    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "pw",
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "n",  # decline pin
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )

    rc = main(["add", "work"])
    assert rc != 0
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_add_does_not_persist_on_validation_failure(
    tmp_config_dir: Path, monkeypatch, capsys
):
    from proton_mcp.exceptions import BridgeRejectedCredentials

    _stub_inputs(
        monkeypatch,
        [
            "alice@proton.me",
            "wrong-pw",
            "127.0.0.1",
            "1143",
            "127.0.0.1",
            "1025",
            "y",
        ],
    )
    monkeypatch.setattr(
        "proton_mcp.auth_cli.probe_fingerprint",
        lambda host, port, timeout=10.0: "f" * 64,
    )
    fake_session = MagicMock()
    fake_session.imap.side_effect = BridgeRejectedCredentials("work")
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["add", "work"])
    assert rc != 0
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_list_prints_label_and_email_rows(
    tmp_config_dir: Path, capsys
):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    write_account_file(tmp_config_dir / "accounts", "personal", "bob@proton.me")

    rc = main(["list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "work" in out
    assert "alice@proton.me" in out
    assert "personal" in out
    assert "bob@proton.me" in out


def test_list_prints_placeholder_when_no_accounts(
    tmp_config_dir: Path, capsys
):
    rc = main(["list"])
    assert rc == 0
    assert "no accounts configured" in capsys.readouterr().out


def test_remove_deletes_token_file(tmp_config_dir: Path, capsys):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    rc = main(["remove", "work"])
    assert rc == 0
    assert "Removed account 'work'" in capsys.readouterr().out
    assert not (tmp_config_dir / "accounts" / "work.json").exists()


def test_remove_unknown_label_exits_nonzero(tmp_config_dir: Path):
    rc = main(["remove", "nope"])
    assert rc != 0


def test_test_command_revalidates_existing_account(
    tmp_config_dir: Path, monkeypatch, capsys
):
    write_account_file(tmp_config_dir / "accounts", "work", "alice@proton.me")
    fake_session = MagicMock()
    fake_session.imap.return_value = MagicMock()
    monkeypatch.setattr(
        "proton_mcp.auth_cli.BridgeSession", lambda rec: fake_session
    )

    rc = main(["test", "work"])
    assert rc == 0
    assert "OK" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_auth_cli.py -v
```

Expected: ImportError on `proton_mcp.auth_cli`.

- [ ] **Step 3: Implement `auth_cli.py`**

Create `src/proton_mcp/auth_cli.py`:

```python
"""proton-mcp-auth: manage local Bridge credentials for the MCP server."""

from __future__ import annotations

import argparse
import getpass
import sys
from collections.abc import Sequence

from proton_mcp import config
from proton_mcp.accounts import AccountRecord, AccountStore
from proton_mcp.bridge import BridgeSession, probe_fingerprint
from proton_mcp.exceptions import (
    AccountNotConfigured,
    ProtonMcpError,
)


def _prompt(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    raw = input(f"{prompt}{suffix}: ").strip()
    if not raw and default is not None:
        return default
    return raw


def _prompt_int(prompt: str, default: int) -> int:
    raw = _prompt(prompt, str(default))
    return int(raw)


def _validate(record: AccountRecord) -> None:
    """Open and close an IMAP session to check credentials and fingerprint."""
    session = BridgeSession(record)
    imap = session.imap()
    try:
        imap.logout()
    except Exception:
        pass


def _cmd_add(label: str) -> int:
    email = _prompt("Proton email")
    if not email:
        print("error: email is required", file=sys.stderr)
        return 1
    bridge_password = getpass.getpass("Bridge app password (hidden): ")
    if not bridge_password:
        print("error: bridge password is required", file=sys.stderr)
        return 1
    imap_host = _prompt("Bridge IMAP host", config.DEFAULT_IMAP_HOST)
    imap_port = _prompt_int("Bridge IMAP port", config.DEFAULT_IMAP_PORT)
    smtp_host = _prompt("Bridge SMTP host", config.DEFAULT_SMTP_HOST)
    smtp_port = _prompt_int("Bridge SMTP port", config.DEFAULT_SMTP_PORT)

    fingerprint = probe_fingerprint(imap_host, imap_port)
    print()
    print("Bridge TLS certificate fingerprint (SHA-256):")
    print(f"  {fingerprint}")
    print(
        "Compare this against Bridge → Settings → Show certificate → SHA-256."
    )
    confirm = _prompt("Pin this fingerprint? (y/n)", "y")
    if confirm.lower() not in {"y", "yes"}:
        print("aborted — fingerprint not confirmed", file=sys.stderr)
        return 1

    record = AccountRecord(
        label=label,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        bridge_password=bridge_password,
        tls_fingerprint_sha256=fingerprint,
    )

    try:
        _validate(record)
    except ProtonMcpError as e:
        print(f"error: validation failed: {e}", file=sys.stderr)
        return 1

    AccountStore().save(
        label=label,
        email=email,
        imap_host=imap_host,
        imap_port=imap_port,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        bridge_password=bridge_password,
        tls_fingerprint_sha256=fingerprint,
    )
    print(f"Saved account '{label}' (email: {email})")
    return 0


def _cmd_list() -> int:
    accounts = AccountStore().list()
    if not accounts:
        print("(no accounts configured)")
        return 0
    width = max(len(a.label) for a in accounts)
    for a in accounts:
        print(f"  {a.label.ljust(width)}  {a.email}")
    return 0


def _cmd_remove(label: str) -> int:
    try:
        AccountStore().remove(label)
    except AccountNotConfigured as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"Removed account '{label}'")
    return 0


def _cmd_test(label: str) -> int:
    try:
        record = AccountStore().load(label)
        _validate(record)
    except ProtonMcpError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"OK — account '{label}' validates against Bridge")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="proton-mcp-auth")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_add = sub.add_parser("add", help="Authenticate and add a new account")
    p_add.add_argument("label", help="Local label (e.g. 'work', 'personal')")
    sub.add_parser("list", help="List configured accounts")
    p_rm = sub.add_parser("remove", help="Remove a configured account")
    p_rm.add_argument("label", help="Account label to remove")
    p_test = sub.add_parser(
        "test", help="Revalidate an existing account against Bridge"
    )
    p_test.add_argument("label", help="Account label to test")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.cmd == "add":
        return _cmd_add(args.label)
    if args.cmd == "list":
        return _cmd_list()
    if args.cmd == "remove":
        return _cmd_remove(args.label)
    if args.cmd == "test":
        return _cmd_test(args.label)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_auth_cli.py -v
uv run pytest -v
uv run ruff check .
uv run mypy
```

Expected: 8 auth_cli tests pass; full suite stays green; lint and mypy clean.

- [ ] **Step 5: Commit**

```bash
git add src/proton_mcp/auth_cli.py tests/test_auth_cli.py
git commit -m "feat(auth_cli): add/list/remove/test commands with TOFU fingerprint pinning"
```

---

## Phase H — E2E + CI + Docs

### Task 15: Add the end-to-end smoke script

**Files:**
- Create: `scripts/e2e_smoke.py`

The script spawns the real `proton-mcp` server as a subprocess and drives it over stdio against a real Bridge account. Each leg cleans up its own artifacts (uuid-tagged subjects) and is idempotent across reruns.

- [ ] **Step 1: Write `scripts/e2e_smoke.py`**

Create `scripts/e2e_smoke.py`:

```python
"""End-to-end smoke test for proton-mcp.

Spawns the real proton-mcp server as a subprocess and drives every tool
surface against a live Proton Bridge over stdio. Run with:

    MCP_E2E_ACCOUNT=test-account uv run python scripts/e2e_smoke.py

Requires that <test-account> already be configured via:
    proton-mcp-auth add test-account
and that Proton Bridge is running locally and signed into that account.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ACCOUNT_ENV = "MCP_E2E_ACCOUNT"


def _tag() -> str:
    return f"proton-mcp-smoke-{uuid.uuid4().hex[:8]}"


async def _call(session: ClientSession, name: str, args: dict) -> object:
    result = await session.call_tool(name, args)
    payload = result.content[0].text
    if payload.startswith("error:"):
        raise RuntimeError(payload)
    return json.loads(payload)


async def _send_search_trash(session: ClientSession, account: str) -> None:
    accounts = await _call(session, "list_accounts", {})
    self_email = next(a["email"] for a in accounts if a["label"] == account)
    tag = _tag()

    print(f"  sending self-email with tag {tag}")
    await _call(
        session,
        "mail_send",
        {
            "account": account,
            "to": self_email,
            "subject": tag,
            "body": "smoke test",
        },
    )

    print("  waiting for delivery, then searching")
    await asyncio.sleep(3)
    hits = await _call(
        session,
        "mail_search",
        {
            "account": account,
            "query": {"subject": tag},
            "folder": "INBOX",
            "max_results": 5,
        },
    )
    if not hits:
        raise RuntimeError(f"sent message with tag {tag} not searchable")

    handle = hits[0]["handle"]
    print(f"  fetching {handle}")
    msg = await _call(session, "mail_get_message", {"account": account, "handle": handle})
    if msg["subject"] != tag:
        raise RuntimeError("get_message round-trip subject mismatch")

    print("  trashing")
    await _call(session, "mail_trash", {"account": account, "handle": handle})


async def _draft_and_delete(session: ClientSession, account: str) -> None:
    tag = _tag()
    print(f"  creating draft tagged {tag}")
    drafted = await _call(
        session,
        "mail_create_draft",
        {
            "account": account,
            "to": "nobody@example.invalid",
            "subject": tag,
            "body": "draft",
        },
    )

    # Find it in Drafts and trash it.
    hits = await _call(
        session,
        "mail_search",
        {
            "account": account,
            "query": {"subject": tag},
            "folder": "Drafts",
            "max_results": 5,
        },
    )
    if not hits:
        raise RuntimeError(f"draft {drafted!r} not visible in Drafts")
    await _call(
        session, "mail_trash", {"account": account, "handle": hits[0]["handle"]}
    )


async def main() -> int:
    account = os.environ.get(ACCOUNT_ENV)
    if not account:
        print(f"set {ACCOUNT_ENV} to the account label to run against.", file=sys.stderr)
        return 1

    params = StdioServerParameters(command="proton-mcp", args=[])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"discovered {len(tools.tools)} tools over stdio")

            print("send → search → trash:")
            await _send_search_trash(session, account)
            print("create draft → trash:")
            await _draft_and_delete(session, account)

    print("smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
```

- [ ] **Step 2: Commit**

```bash
git add scripts/e2e_smoke.py
git commit -m "test(e2e): end-to-end smoke that drives the server via stdio against Bridge"
```

The smoke script is not part of `pytest` — it's opt-in. Documented in the README in Task 17.

---

### Task 16: Add CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Write `.github/workflows/ci.yml`**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  ci:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: uv sync

      - name: Lint (ruff)
        run: uv run ruff check .

      - name: Type-check (mypy)
        run: uv run mypy

      - name: Test (pytest)
        run: uv run pytest -v
```

- [ ] **Step 2: Verify locally**

```bash
uv run ruff check .
uv run mypy
uv run pytest -v
```

Expected: all three commands green.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: ruff + mypy + pytest on push/PR"
```

---

### Task 17: Write README and CLAUDE.md

**Files:**
- Create: `README.md`
- Create: `CLAUDE.md`

- [ ] **Step 1: Write `README.md`**

Create `README.md`:

````markdown
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

In the Bridge app, open the account view. You need four things:

- **Email address** (e.g. `alice@proton.me`)
- **Bridge IMAP/SMTP password** (a long random string Bridge generates —
  not your Proton login password)
- **IMAP host:port** (default `127.0.0.1:1143`)
- **SMTP host:port** (default `127.0.0.1:1025`)
- **TLS certificate SHA-256 fingerprint**: Bridge → Settings → "Show
  certificate" → SHA-256. Copy this. We'll pin it on first add so the
  server refuses to talk to any other process that ends up on those ports.

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

List configured accounts:

```bash
proton-mcp-auth list
```

Remove or revalidate:

```bash
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
````

- [ ] **Step 2: Write `CLAUDE.md`**

Create `CLAUDE.md`:

````markdown
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

`_invoke_tool` wraps every handler call and translates failures into a
stable `"error: ..."` text payload — `ProtonMcpError` verbatim,
`ValueError`/`TypeError` as "invalid arguments", anything else as
"internal error". The MCP transport never sees a Python exception.
Preserve this convention when adding tools.

### Layering: `tools/` vs `shaping/`

- `tools/mail.py` — calls IMAP/SMTP via `BridgeSession`, hands raw RFC822
  bytes or `imapclient` dicts to shaping.
- `shaping/mail.py` — pure functions that compact RFC822 into the small
  dicts returned to the model. **Keep IMAP/SMTP calls out of `shaping/`**
  and keep payload-massaging out of `tools/`; shaping tests in
  `tests/shaping/` rely on this split.

### Bridge connection layer (`bridge.py`)

`BridgeSession` is the single boundary between the tool layer and the
network. Per tool call, the tool function builds `BridgeSession.for_account
(label)`-equivalent (`BridgeSession(record)`), calls `.imap()` or `.smtp()`,
and `.logout()`/`.quit()` in a `finally`. No global connection cache.

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
````

- [ ] **Step 3: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: README + CLAUDE.md"
```

---

### Task 18: Write the Claude Desktop install runbook

**Files:**
- Create: `agents/install/claude-desktop.md`

This runbook is intended for an AI agent running locally inside a clone of
this repo, helping a possibly-non-technical user install everything
end-to-end. It mirrors the structure of the multi-google-mcp runbook.

- [ ] **Step 1: Write `agents/install/claude-desktop.md`**

Create `agents/install/claude-desktop.md`:

````markdown
# Install `proton-mcp` into Claude Desktop — Agent Runbook

> **Audience:** You are an AI agent (Claude Desktop, Claude Code, Cursor, etc.) running locally inside a clone of the `proton-mcp` repo. The human in front of you has asked you to install this server. Follow this runbook end-to-end. The user may have little or no experience with the command line — be patient.

## How to read this runbook

- Each phase has named blocks: **Detection**, **Commands**, **User-facing template**, **Failure**, **Exit ramp**.
- Do **one phase at a time**. Inside phases with sub-phases (Phase 1), do **one sub-phase per turn**.
- Never claim a step succeeded without either explicit user confirmation OR an objective state check.
- Read everything in **Commands** literally — do not improvise URLs, paths, or flags.

## Tone & pacing

- Short messages. One micro-step at a time.
- Plain English. First use of jargon ("IMAP", "TLS fingerprint") gets a one-sentence parenthetical explanation.
- Patient and supportive — retrying is fine, say so explicitly.

---

## Phase 0 — Preflight

Detect what's already done so you can resume mid-flow on a rerun.

### Detection

Run all six checks in parallel:

```bash
# 1. Proton Bridge installed (macOS path; Windows/Linux differ)
test -d "/Applications/Proton Mail Bridge.app" || \
  test -d "$HOME/Applications/Proton Mail Bridge.app"

# 2. Bridge IMAP port is reachable
nc -z -G 2 127.0.0.1 1143

# 3. uv on PATH
command -v uv

# 4. proton-mcp CLI installed
command -v proton-mcp && command -v proton-mcp-auth

# 5. At least one account configured
find ~/.config/proton-mcp/accounts -maxdepth 1 -name '*.json' 2>/dev/null | head -1

# 6. proton server already wired into Claude Desktop config
jq -e '.mcpServers["proton"]' \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
  2>/dev/null
```

### User-facing template

> "Let me look at what's already in place — one moment.
>
> - [✓/✗] Proton Mail Bridge installed
> - [✓/✗] Bridge IMAP reachable at 127.0.0.1:1143
> - [✓/✗] `uv` installed
> - [✓/✗] `proton-mcp` CLI installed
> - [✓/✗] At least one Proton account connected
> - [✓/✗] `proton` server wired into Claude Desktop
>
> I'll start at the earliest red phase. Sound good?"

### Decision logic

- All six green → Phase 6 (verify + restart).
- Check 6 red only → Phase 5 (wire into config).
- Checks 4, 5, 6 red → Phase 4 (add account).
- Checks 3, 4, 5, 6 red → Phase 3 (install CLI).
- Check 2 red, others ok → Phase 1 sub-phase 1d (Bridge not running) before installing the CLI.
- Check 1 red → Phase 1 (install Bridge).

---

## Phase 1 — Install Proton Bridge

This is the longest user-facing phase. Walk through one sub-phase per turn.

### Sub-phase 1a — Confirm a paid Proton plan

**User-facing template:**

> "Before we start: Proton Mail Bridge requires a **paid** Proton plan (Mail Plus or higher). Are you on a paid plan? If you're not sure, sign in at <https://account.proton.me/> and the Subscription page tells you.
>
> Reply 'yes', 'no', or 'not sure' and I'll guide you from there."

- **yes** → continue to 1b.
- **no** → Tell the user: *"Bridge isn't available on the free plan. The Proton team will let you upgrade at <https://account.proton.me/upgrade>. If you'd rather not upgrade, this server can't connect to your account — let me know how you'd like to proceed."* Halt the runbook.
- **not sure** → tell them to check the URL above and report back.

### Sub-phase 1b — Download and install Bridge

**Commands:**

```bash
# macOS only — open the download page
open https://proton.me/mail/bridge
```

**User-facing template:**

> "Open the Bridge download page (I just tried to open it for you). Download the macOS installer (or Windows / Linux as appropriate), open it, and drag Proton Mail Bridge to Applications. Let me know once it's installed."

**Checkpoint:** User confirms Bridge is in Applications.

### Sub-phase 1c — Sign into Bridge

**User-facing template:**

> "Open Proton Mail Bridge from Applications. Sign in with the Proton account you want to connect. Bridge will start syncing your mailbox — this can take a few minutes the first time. Let me know when it shows 'Connected' / 'Syncing complete'."

**Checkpoint:** User confirms Bridge shows the account as connected.

### Sub-phase 1d — Find Bridge's app password and TLS fingerprint

**User-facing template:**

> "Inside Bridge, click the gear icon (or the three-dot menu) on your account row and choose 'Mailbox Details' (or 'Configure'). You'll see:
>
> - **IMAP host/port** — should be `127.0.0.1:1143`
> - **SMTP host/port** — should be `127.0.0.1:1025`
> - **Username** — your Proton email
> - **Password** — a long random string (this is the **app password**; it's NOT your Proton login password)
>
> Copy the password somewhere safe — you'll paste it in a moment.
>
> Now open Bridge → Settings → Show certificate (or 'Advanced settings'). You'll see a SHA-256 fingerprint that looks like `xx:xx:xx:...` or a long hex string. Keep that visible too — we'll compare it.
>
> Let me know when you have the password and the fingerprint in front of you."

**Checkpoint:** User confirms they have the password + fingerprint.

---

## Phase 2 — Install `uv`

### Detection

```bash
command -v uv
```

### User-facing template

> "I don't see `uv` installed yet. `uv` is a fast Python package manager.
>
> Paste this into your terminal:
>
> ```
> curl -LsSf https://astral.sh/uv/install.sh | sh
> ```
>
> Let me know once it finishes (10–30 seconds)."

### Failure

- New shell may need `source ~/.zshrc` (or a fresh terminal).
- If still missing, ask for the install output.

---

## Phase 3 — Install the CLI

### Detection

```bash
command -v proton-mcp && command -v proton-mcp-auth
```

### Commands

```bash
cd "$(git rev-parse --show-toplevel)" && uv tool install .
```

### User-facing template

> "Installing the server CLI now. This puts two commands on your PATH:
> - `proton-mcp` — the server itself (Claude Desktop will start it)
> - `proton-mcp-auth` — for adding Proton accounts
>
> Running it…"

---

## Phase 4 — Add the first Proton account

### Detection

```bash
find ~/.config/proton-mcp/accounts -maxdepth 1 -name '*.json' 2>/dev/null | head -1
```

If any account file is printed, skip to Phase 5.

### Commands

Ask the user for a label (suggest `personal`), then:

```bash
proton-mcp-auth add <label>
```

### User-facing template

> "Time to connect your first Proton account. Pick a short label like 'personal' or 'work'.
>
> What label would you like?"

After they choose, run `proton-mcp-auth add <label>` and walk them through the prompts:

> "The CLI is going to ask you a few things — answer in this order:
>
> 1. **Proton email** — `you@proton.me`
> 2. **Bridge app password** — paste the long random string from Bridge (it will be hidden as you type)
> 3. **Bridge IMAP host** — press Enter to accept the default `127.0.0.1`
> 4. **Bridge IMAP port** — press Enter for `1143`
> 5. **Bridge SMTP host** — press Enter for `127.0.0.1`
> 6. **Bridge SMTP port** — press Enter for `1025`
> 7. **Fingerprint confirmation** — the CLI shows you the certificate fingerprint it just fetched. **Compare it character-for-character** with what Bridge → Show certificate shows. If they match, type `y`. If they don't match, type `n` and let me know — that means something else is impersonating Bridge.
>
> After you confirm, the CLI does a quick IMAP login to make sure the password works, then saves the credentials. Tell me how it goes."

### Verification

```bash
test -f ~/.config/proton-mcp/accounts/<label>.json
jq -e '.bridge_password != null' ~/.config/proton-mcp/accounts/<label>.json >/dev/null
```

**Never** run `jq '.bridge_password' …` without `>/dev/null` — that prints the password to the conversation transcript.

### Failure

- **`Cannot reach Bridge at 127.0.0.1:1143`** → Bridge isn't running. Ask the user to open Bridge and retry.
- **`Bridge rejected credentials`** → Wrong app password. Have them copy the password again from Bridge and rerun.
- **Fingerprint mismatch on confirmation prompt** → Something is suspicious. Ask the user to read both fingerprints aloud (or paste them) — diagnose whether they were comparing the right bridge cert or maybe a different cert pane.

---

## Phase 5 — Wire the server into Claude Desktop's config

### Detection

```bash
jq -e '.mcpServers["proton"]' \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
  2>/dev/null >/dev/null
```

If exit 0, verify the stored command exists:

```bash
STORED_CMD="$(jq -r '.mcpServers["proton"].command' \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json")"
[ -x "$STORED_CMD" ]
```

If both pass, skip to Phase 6.

### Commands

**Path:** `$HOME/Library/Application Support/Claude/claude_desktop_config.json` (macOS).
(Windows: `%APPDATA%\Claude\…`; Linux: `~/.config/Claude/…`.)

**Read-merge-write logic:**

1. Resolve the absolute path: `PMCP_BIN="$(command -v proton-mcp)"`.
2. If the config doesn't exist, write `{"mcpServers": {"proton": {"command": "<PMCP_BIN>"}}}`.
3. If it exists, parse it. **If parse fails, stop** and surface the error — never overwrite a malformed config.
4. Set `.mcpServers["proton"] = {"command": "<PMCP_BIN>"}`. Preserve every other key.
5. Write back with 2-space indent. Make a timestamped backup first.

The `jq` one-liner:

```bash
CFG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
PMCP_BIN="$(command -v proton-mcp)"
[ -n "$PMCP_BIN" ] || { echo "proton-mcp not on PATH — rerun Phase 3 first."; exit 1; }
mkdir -p "$(dirname "$CFG")"
test -f "$CFG" || echo '{}' > "$CFG"
cp "$CFG" "${CFG}.bak.$(date +%Y%m%d-%H%M%S)"
TMP="$(mktemp)"
jq --arg cmd "$PMCP_BIN" '.mcpServers["proton"] = {"command": $cmd}' "$CFG" > "$TMP" \
  && mv "$TMP" "$CFG"
```

> **Why an absolute path?** Claude Desktop launched from Finder/Dock inherits launchd's minimal PATH (`/usr/bin:/bin:/usr/sbin:/sbin`), not your shell's. `uv tool install` places binaries in `~/.local/bin/`, which is on your shell PATH but not on the GUI's. The bare command `"proton-mcp"` works in a terminal but fails when Claude Desktop launches it.

### User-facing template

> "Adding the server to Claude Desktop's config. I'll merge with whatever's already there, back up the previous version, and use the absolute path so the GUI launcher finds the binary."

### Verification

```bash
STORED_CMD="$(jq -r '.mcpServers["proton"].command' \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json")"
[ -n "$STORED_CMD" ] && [ -x "$STORED_CMD" ]
```

---

## Phase 6 — Verify and restart

### User-facing template

> "Two final steps.
>
> **Step 1: Fully quit Claude Desktop.** Cmd+Q (not just closing the window). Reopen.
>
> **Step 2: Test a tool call.** Try a prompt like:
>
> *"Use proton to search my `<your-label>` inbox for unread messages from this week."*
>
> If Claude calls a tool starting with `mail_` (you'll see it in the conversation), the install worked. Tell me what happens."

### Failure modes

**Tools don't appear:**

1. Confirm Claude Desktop fully restarted.
2. Run `proton-mcp` manually:
   ```bash
   proton-mcp
   ```
   Should print nothing and wait on stdin (Ctrl-C to exit). If it errors, surface the message — likely a credentials issue.
3. Verify config:
   ```bash
   jq '.mcpServers["proton"]' \
     "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
   ```
4. Check Claude Desktop's logs (Help → View Logs) for a startup error.

**`error: cannot reach Bridge at 127.0.0.1:1143`:**

Bridge isn't running. Open the Bridge app. (And consider asking the user whether they want Bridge to launch at login — they'd set that in Bridge's Settings.)

**`error: Bridge TLS fingerprint ... does not match`:**

Bridge regenerated its certificate. Have them rerun `proton-mcp-auth add <label>` to re-pin.

---

## You're done

When Phase 6 succeeds, tell the user:

> "All set. Your `proton-mcp` install is wired into Claude Desktop. A few useful follow-ups:
>
> - **Add another account:** `proton-mcp-auth add <new-label>`
> - **List configured accounts:** `proton-mcp-auth list`
> - **Remove an account:** `proton-mcp-auth remove <label>`
> - **Revalidate after a Bridge reset:** `proton-mcp-auth test <label>`
> - **Troubleshooting:** see the project README.
>
> Happy to help if anything goes sideways later."
````

- [ ] **Step 2: Commit**

```bash
git add agents/install/claude-desktop.md
git commit -m "docs: Claude Desktop install runbook"
```

---

### Task 19: Final sanity check

- [ ] **Step 1: Run the full suite**

```bash
uv run ruff check .
uv run mypy
uv run pytest -v
```

Expected: all three pass.

- [ ] **Step 2: Verify the CLI is installable**

```bash
uv tool install .
proton-mcp-auth --help
proton-mcp --help 2>&1 | head -1 || true
```

Expected: `proton-mcp-auth --help` prints the subcommand help. `proton-mcp --help` may exit non-zero (argparse free; the server waits on stdin). That's fine — it's wired via Claude Desktop's stdio, not the terminal.

- [ ] **Step 3: Push to GitHub (optional, only if user wants a remote)**

```bash
# Ask the user first; do not push without explicit go-ahead.
git remote add origin <url>
git push -u origin main
```

If pushing, CI runs and should pass (it mirrors the local commands).

---

## Done

When all 19 tasks are complete:

- The server installs as `proton-mcp` + `proton-mcp-auth` via `uv tool install .`
- Unit tests pass with no network access
- The E2E smoke (with `MCP_E2E_ACCOUNT` set) drives the whole stack against a real Bridge
- Claude Desktop sees 10 tools and can read/edit Proton mail through them
- An AI agent can walk a non-technical user through the entire install via `agents/install/claude-desktop.md`

Follow-up work (out of v1 scope, tracked in the spec §13 and §18):

- Codex CLI install runbook
- Free-tier fallback via `hydroxide`
- Proton Calendar / Drive / Pass / VPN surfaces
