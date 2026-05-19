# Codex CLI install runbook for proton-mcp — Design

**Date:** 2026-05-19
**Status:** Draft, pending user review
**Target audience:** Non-technical end-users running an AI agent in Codex
CLI inside a local clone of this repo, who want the agent to install and
configure `proton-mcp` for them end-to-end.

**Relationship to existing docs:**
The parent project spec
(`docs/superpowers/specs/2026-05-19-proton-mcp-design.md`) explicitly
deferred Codex CLI support to a follow-up. The Claude Desktop runbook at
`agents/install/claude-desktop.md` shipped with v1. This spec covers the
follow-up: a Codex-targeted sibling runbook.

This spec also imports decisions wholesale from
`../multi-google-mcp/docs/superpowers/specs/2026-05-19-agent-install-runbook-design.md`.
Where that spec mandates a pattern (read-merge-write, awk-based in-place
TOML rewrite, absolute-path resolution via `command -v`), this spec
follows it verbatim.

---

## 1. Goal

Add `agents/install/codex.md` so an AI agent running inside a clone of
this repo can install `proton-mcp` for a non-technical user in Codex
CLI, end-to-end — including Proton Bridge install/sign-in, account
add, and Codex config wiring — with patient, hand-holding pacing and
clean exit ramps if the user can't finish in one sitting.

Priority order for harness coverage (carried forward from the parent
spec):

1. **Claude Desktop** — already shipped in v1
   (`agents/install/claude-desktop.md`).
2. **Codex CLI** — this PR.
3. **OpenClaw / Hermes / others** — out of scope. Same structure will
   apply when they land.

## 2. Non-goals

- No new automation script. The runbook *is* the automation surface;
  the agent executes shell commands and file edits directly.
- No changes to existing server code, tool behavior, CLI commands, or
  the Claude Desktop runbook.
- No removal of the existing manual install instructions in the README
  — those stay for users who prefer a manual path.
- No support for harnesses beyond Claude Desktop and Codex in this PR.
- No automated test for markdown content. Verification is by reviewer
  read-through plus a manual end-to-end smoke test against a real
  Codex install.

## 3. Audience and tone

Identical to the Claude Desktop runbook: the runbook is written for
**agents reading it in-conversation**, not for humans reading it top-to-
bottom. The agent reads the runbook, then talks to the user in short,
patient, supportive messages.

Tone & pacing principles:

- **One step at a time.** Never dump a multi-step block on the user.
  Each micro-step is its own user-facing message ending in a clear
  checkpoint.
- **Reassurance after every checkpoint.** When the user reports
  success, acknowledge it before moving forward.
- **No jargon unless defined.** First use of "TLS fingerprint", "Bridge
  app password", etc. gets a one-sentence parenthetical.
- **Never claim done without proof.** Either the user confirms OR the
  agent verifies state via a command.

## 4. File layout

This PR adds one new file and modifies the README and (optionally) the
parent spec/plan:

```
agents/
└── install/
    ├── claude-desktop.md     # UNCHANGED (already shipped)
    └── codex.md              # NEW — Codex CLI runbook

README.md                     # MODIFIED — replace the "coming in a
                              # follow-up" placeholder with a link
```

## 5. Runbook structure

The Codex runbook follows the same 7-phase linear structure as the
Claude Desktop runbook. Phases 0–4 and 6 are essentially identical;
Phase 5 differs because Codex uses TOML, not JSON.

### 5.1 Phase skeleton

| Phase | Purpose |
|---|---|
| **0. Preflight** | Detect prior state so the agent can resume mid-flow. The harness-specific check now grep's `~/.codex/config.toml` for `[mcp_servers.proton]` instead of jq'ing the Claude Desktop JSON. |
| **1. Install Proton Bridge** | Same four sub-phases as Claude Desktop: paid-plan check (1a), download (1b), sign-in (1c), find app password + TLS fingerprint (1d). |
| **2. Install `uv`** | Same. |
| **3. Install the CLI** | Same — `uv tool install .` from repo root, confirm `proton-mcp` and `proton-mcp-auth` on PATH. |
| **4. Add first Proton account** | Same — `proton-mcp-auth add <label>` with fingerprint confirmation, verify `~/.config/proton-mcp/accounts/<label>.json` exists. |
| **5. Wire into Codex config** | **Differs.** Edit `~/.codex/config.toml`, append-or-replace a `[mcp_servers.proton]` section with the absolute path to the `proton-mcp` binary. Always back up before writing. |
| **6. Verify and restart** | Conversational only. Tell user to start a new `codex` session and test with a `mail_*` tool prompt. |

### 5.2 Per-phase block structure

Inside each phase, the same five named blocks as the parent design:

1. **Detection** — exact shell commands the agent runs to determine
   "already done" vs "needs doing." Idempotency lives here.
2. **Commands** — the literal shell commands or file-edit specs the
   agent executes.
3. **User-facing template** — plain-language message at each
   checkpoint.
4. **Failure** — diagnostic and retry guidance.
5. **Exit ramp** — how the user can pause and resume.

## 6. Phase 5 — Codex variant detail

This is the only structurally novel phase relative to the existing
Claude Desktop runbook in this repo. The pattern is lifted from
`../multi-google-mcp/agents/install/codex.md`.

**Path:** `~/.codex/config.toml`.

**Format:** TOML. Codex's MCP config uses `[mcp_servers.<name>]`
sections.

**Schema for the new entry (`<PMCP_BIN>` is the absolute path resolved
at write time from `command -v proton-mcp`, typically
`/Users/<you>/.local/bin/proton-mcp` after `uv tool install`):**

```toml
[mcp_servers.proton]
command = "<PMCP_BIN>"
```

**Append-or-replace logic:**

1. Resolve `PMCP_BIN="$(command -v proton-mcp)"`. Bail if empty.
2. Ensure parent directory exists: `mkdir -p ~/.codex`.
3. If `~/.codex/config.toml` does not exist: create it with only the
   new section.
4. If it exists AND has the `[mcp_servers.proton]` section: rewrite
   that section in place via an awk pass that preserves blank lines
   and other sections.
5. If it exists AND does not have the section: append a leading blank
   line followed by the new section.
6. Always make a timestamped backup before writing.

**Why an absolute path?** Codex inherits the shell PATH when launched
from a login terminal, but not under launchd, GUI wrappers, or
non-login shells. Resolving the absolute path with `command -v` at
write time makes the config robust across all launch contexts.

**Verification:** `grep -q '^\[mcp_servers\.proton\]' ~/.codex/config.toml`
matches, the command extracted with sed is non-empty, and the
extracted path passes `[ -x "$STORED_CMD" ]`.

## 7. README change

Find the line `**Codex CLI** — coming in a follow-up.` and replace it
with a markdown link entry parallel to the existing Claude Desktop
line:

```markdown
- **Codex CLI** — [`agents/install/codex.md`](agents/install/codex.md)
```

Nothing else in the README changes. The "Quick install" section's
intro paragraph already announces both harnesses by description; only
the bullet that pointed to nothing needs to point somewhere now.

## 8. Verification plan for this PR

Markdown-only PR, but the runbook is *executable* in the sense that an
agent runs each command while reading it. So verification means
following the runbook end-to-end on a real machine.

**Manual review pass:**

- The single new file is structurally parallel to
  `agents/install/claude-desktop.md` — same heading hierarchy, same
  five-block phase structure.
- Phase 5's awk script is correct: it preserves other sections, exits
  the in-section state on either a new `[section]` header or a blank
  line, and emits the rewritten section with the absolute path.
- Phase 6's user-facing template references `codex` (not Claude
  Desktop) consistently.
- All shell commands are valid bash with proper quoting (no spaces in
  the Codex paths means quoting is less load-bearing than in the
  Claude Desktop runbook, but commands should still pass shellcheck-
  by-eye).
- README link to `agents/install/codex.md` resolves to a real file.

**End-to-end smoke test (developer machine):**

- Start with a clean state (or accurately preflight-detected partial
  state). Walk through the runbook one phase at a time. At each
  checkpoint, confirm the verification command succeeds before moving
  to the next phase.
- Specifically smoke Phase 5 by:
  1. Running it against a `~/.codex/config.toml` that already contains
     unrelated `[mcp_servers.foo]` and `[other_section]` entries.
     Confirm the awk pass preserves everything else.
  2. Running it against a non-existent `~/.codex/config.toml`.
     Confirm the new file is well-formed TOML with only the proton
     section.
- Phase 6: open a fresh `codex` session, ask it to use proton to do
  something simple, confirm a `mail_*` tool is called.

**Automated test changes:** None. Existing `pytest` / `ruff` / `mypy`
runs on Phase 3 of `/code-task` are unaffected by markdown-only
changes.

**Per `/code-task` Phase 2.6:** Docs-only commits must call out the
absence of new tests in the commit body.

## 9. Open questions / deferred decisions

- **Windows/Linux paths.** macOS-tested only. The runbook is intended
  for macOS; the file path `~/.codex/config.toml` is the same on
  Linux/WSL so most of the runbook works there too, but no Windows
  smoke test is in scope.
- **OpenClaw / Hermes runbooks.** Out of scope.
- **Parent spec amendment.** The parent spec (§13 of
  `2026-05-19-proton-mcp-design.md`) historically documented the
  Codex deferral. Rather than rewrite history, this follow-up spec
  documents the un-deferral. The parent spec's deferral text stays as
  a historical record of that decision.
