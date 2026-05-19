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
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ACCOUNT_ENV = "MCP_E2E_ACCOUNT"


def _tag() -> str:
    return f"proton-mcp-smoke-{uuid.uuid4().hex[:8]}"


async def _call(session: ClientSession, name: str, args: dict[str, Any]) -> Any:
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
    msg = await _call(
        session, "mail_get_message", {"account": account, "handle": handle}
    )
    if msg["subject"] != tag:
        raise RuntimeError("get_message round-trip subject mismatch")

    print("  trashing")
    await _call(session, "mail_trash", {"account": account, "handle": handle})


async def _draft_and_delete(session: ClientSession, account: str) -> None:
    tag = _tag()
    print(f"  creating draft tagged {tag}")
    await _call(
        session,
        "mail_create_draft",
        {
            "account": account,
            "to": "nobody@example.invalid",
            "subject": tag,
            "body": "draft",
        },
    )

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
        raise RuntimeError(f"draft {tag!r} not visible in Drafts")
    await _call(
        session, "mail_trash", {"account": account, "handle": hits[0]["handle"]}
    )


async def main() -> int:
    account = os.environ.get(ACCOUNT_ENV)
    if not account:
        print(
            f"set {ACCOUNT_ENV} to the account label to run against.",
            file=sys.stderr,
        )
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
