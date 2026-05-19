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
