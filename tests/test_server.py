from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

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
    """Sanity: the Server instance returned by build_app declares the right
    number of tools. (We can't call decorator-registered handlers
    directly without setting up the MCP request machinery, so just check
    that the constructor succeeds and TOOL_REGISTRY is the source of
    truth.)"""
    app = build_app()
    assert app.name == "proton-mcp"
    # The handlers are registered as decorators; verify they're present.
    from mcp.types import CallToolRequest, ListToolsRequest

    assert ListToolsRequest in app.request_handlers
    assert CallToolRequest in app.request_handlers
