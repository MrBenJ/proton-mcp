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
        "description": (
            "List IMAP folders on the account, including special-use kinds."
        ),
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
            "Search a folder with a structured query. query keys: from, to, "
            "cc, subject, text, since, before, seen, flagged, answered."
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
        "description": (
            "Download one attachment as base64. "
            "Capped per MAX_ATTACHMENT_BYTES."
        ),
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
            "Add or remove IMAP flags (\\Seen, \\Flagged, \\Answered, "
            "\\Draft)."
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
        "description": (
            "Move a message into another folder (IMAP MOVE or COPY+EXPUNGE)."
        ),
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
    """Resolve the registry entry and call its handler.

    Indirected so tests can patch one symbol to simulate any failure mode
    in the error funnel below.
    """
    entry = next((t for t in TOOL_REGISTRY if t["name"] == name), None)
    if entry is None:
        raise KeyError(name)
    return entry["handler"](arguments or {})


def _invoke_tool(name: str, arguments: dict[str, Any]) -> str:
    """Run a tool by name and return JSON output or an error: text payload.

    Every plausible operational failure converts to a stable "error: ..."
    string so the MCP transport never sees a Python exception. Categories:

    - ProtonMcpError: account / bridge / size errors, message verbatim.
    - ValueError / TypeError: malformed arguments.
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
