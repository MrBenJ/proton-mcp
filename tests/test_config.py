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
    assert config.MAX_INBOUND_BYTES == 25 * 1024 * 1024
