# Codex CLI install runbook — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `agents/install/codex.md` — an agent-targeted Codex CLI install runbook that mirrors `agents/install/claude-desktop.md`, plus a one-line README change pointing at the new file.

**Architecture:** One new markdown file produced by copying the existing Claude Desktop runbook and editing four sites: (1) title + audience line, (2) Phase 0 detection check #6, (3) Phase 5 entirely (JSON merge → TOML append-or-replace via awk), and (4) Phase 6 user-facing template + the "You're done" closer. README's "Codex CLI — coming in a follow-up." line becomes a real link.

**Tech Stack:** Markdown only. The runbook describes shell commands (`grep`, `awk`, `sed`, `command -v`, `cp`) and a TOML file shape — no Python is touched.

---

## File Structure

**New files:**
- `agents/install/codex.md` — Codex CLI runbook, 7 phase sections, mirrors `claude-desktop.md` except Phase 5 and harness-specific lines in Phase 0/6/closing.

**Modified files:**
- `README.md` — single bullet under the "Quick install" section.

**Already-written (commit-only):**
- `docs/superpowers/specs/2026-05-19-codex-install-runbook-design.md` — written during brainstorming; needs to land in this PR's first commit.

**Out of scope this PR:**
- OpenClaw / Hermes runbooks.
- Any change to `agents/install/claude-desktop.md`.
- Any change to server code, tests, or CLI commands.

---

## Task verification reference

**Repo paths used across tasks:**
- Repo root: `/Users/bjunya/code/proton-mcp`
- Source runbook to adapt: `agents/install/claude-desktop.md`
- New runbook target: `agents/install/codex.md`
- Codex config path the runbook writes to: `$HOME/.codex/config.toml`
- README: `README.md`

**TDD applicability:** Per `/code-task` Phase 2.6 — this is documentation-only work. No new tests. Each commit body explicitly says "No test added — documentation-only change." Existing `pytest` / `ruff` / `mypy` runs in `/code-task` Phase 3 must still pass unchanged because no Python is touched.

**Verification per task:** Each task ends with a step that confirms either (a) the file content reads correctly when re-opened, or (b) shell commands cited in that section actually execute cleanly when run by hand.

---

## Task 1: Commit the design spec

**Files:**
- Modify: none — the file `docs/superpowers/specs/2026-05-19-codex-install-runbook-design.md` was written during brainstorming and is currently untracked.

- [ ] **Step 1: Confirm the spec file exists and is unstaged**

Run:
```bash
git status docs/superpowers/specs/2026-05-19-codex-install-runbook-design.md
```

Expected: shows the file as untracked (or modified if a prior run staged it).

- [ ] **Step 2: Stage and commit the spec**

```bash
git add docs/superpowers/specs/2026-05-19-codex-install-runbook-design.md
git commit -m "$(cat <<'EOF'
docs: add design spec for Codex CLI install runbook

Captures the decision to write agents/install/codex.md as a follow-up
to the Claude Desktop runbook shipped in v1. Imports the read-merge-
write and absolute-path patterns from the multi-google-mcp codex
runbook spec.

No test added — documentation-only change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 3: Verify the commit landed**

```bash
git log -1 --oneline
```

Expected: shows a commit with the message above. `git status` should now be clean (or only show files this plan modifies in later tasks).

---

## Task 2: Create `agents/install/codex.md` from the Claude Desktop runbook

**Files:**
- Create: `agents/install/codex.md` (initially identical to `agents/install/claude-desktop.md`).

- [ ] **Step 1: Copy the source file**

```bash
cp /Users/bjunya/code/proton-mcp/agents/install/claude-desktop.md \
   /Users/bjunya/code/proton-mcp/agents/install/codex.md
```

- [ ] **Step 2: Confirm the file exists and matches the source**

```bash
test -f /Users/bjunya/code/proton-mcp/agents/install/codex.md
diff /Users/bjunya/code/proton-mcp/agents/install/claude-desktop.md \
     /Users/bjunya/code/proton-mcp/agents/install/codex.md
```

Expected: `test -f` succeeds with exit 0; `diff` produces no output (the files are byte-identical at this point).

- [ ] **Step 3: Do NOT commit yet**

The file is currently a verbatim copy of `claude-desktop.md`. It becomes Codex-specific only after Task 3's edits. Committing now would land a misleading "added codex runbook" commit that's just a copy. We commit once at the end of Task 3, when the file is genuinely Codex-specific.

---

## Task 3: Edit `agents/install/codex.md` for Codex specifics

**Files:**
- Modify: `agents/install/codex.md` — four targeted edits described below.

These edits use the `Edit` tool with exact `old_string` / `new_string` matches. Apply them in order; later edits depend on earlier ones not having shifted the surrounding context.

- [ ] **Step 1: Replace the title and audience line**

**old_string:**

```
# Install `proton-mcp` into Claude Desktop — Agent Runbook

> **Audience:** You are an AI agent (Claude Desktop, Claude Code, Cursor, etc.) running locally inside a clone of the `proton-mcp` repo. The human in front of you has asked you to install this server. Follow this runbook end-to-end. The user may have little or no experience with the command line — be patient.
```

**new_string:**

```
# Install `proton-mcp` into Codex CLI — Agent Runbook

> **Audience:** You are an AI agent (Codex CLI, Claude Code, Cursor, etc.) running locally inside a clone of the `proton-mcp` repo. The human in front of you has asked you to install this server. Follow this runbook end-to-end. The user may have little or no experience with the command line or TOML — be patient.
```

- [ ] **Step 2: Replace Phase 0 detection check #6**

The Phase 0 detection block ends with a `jq` check on Claude Desktop's JSON config. Swap it for a `grep` on Codex's TOML config.

**old_string:**

```
# 6. proton server already wired into Claude Desktop config
jq -e '.mcpServers["proton"]' \
  "$HOME/Library/Application Support/Claude/claude_desktop_config.json" \
  2>/dev/null
```

**new_string:**

```
# 6. proton server already wired into Codex config
grep -q '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" 2>/dev/null
```

- [ ] **Step 3: Update Phase 0's user-facing template bullet for the harness check**

**old_string:**

```
> - [✓/✗] `proton` server wired into Claude Desktop
```

**new_string:**

```
> - [✓/✗] Codex config file present at `~/.codex/config.toml`
> - [✓/✗] `proton` server wired into Codex
```

(This collapses a single bullet into two — surfacing the existence of the config file as its own check, consistent with the multi-google codex runbook.)

- [ ] **Step 4: Replace Phase 5 entirely**

Locate the entire `## Phase 5` section. The boundary on the top side is the `## Phase 5 — Wire the server into Claude Desktop's config` heading. The boundary on the bottom side is the `---` separator immediately before `## Phase 6 — Verify and restart`. Replace everything inside (heading-line through the `---` exclusive) with the Codex variant.

**old_string** (the full Phase 5 section):

```
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

```

**new_string** (the Codex Phase 5):

```
## Phase 5 — Wire the server into Codex's config

Codex reads MCP server definitions from `~/.codex/config.toml`. We append a `[mcp_servers.proton]` section to that file. **Critically, we preserve everything that's already there — never rewrite the whole file.**

### Detection

```bash
grep -q '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" 2>/dev/null
```

If this matches, also extract the stored command and verify it points at an executable:

```bash
STORED_CMD="$(grep -A2 '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" \
  | sed -n 's/^command = "\(.*\)"$/\1/p' | head -1)"
[ -n "$STORED_CMD" ] && [ -x "$STORED_CMD" ]
```

If both pass, skip to Phase 6. If the section exists but `STORED_CMD` isn't executable (typical with a bare-name install pre-this-runbook), continue with Phase 5 to overwrite with the absolute path.

### Commands

**Path:** `$HOME/.codex/config.toml`.

**Why an absolute path?** Codex inherits the shell PATH when launched from a login terminal, but not under launchd, GUI wrappers, or non-login shells. `uv tool install` places binaries in `~/.local/bin/`, which is on your shell PATH but not necessarily on every launch context's. We resolve the absolute path via `command -v` at write time so the config is robust across all launch contexts.

**Backup before write:**

```bash
CFG="$HOME/.codex/config.toml"
test -f "$CFG" && cp "$CFG" "${CFG}.bak.$(date +%Y%m%d-%H%M%S)"
```

**Append-or-replace logic:**

1. Resolve `PMCP_BIN="$(command -v proton-mcp)"`. Bail if empty.
2. Ensure the parent directory exists: `mkdir -p ~/.codex`.
3. If `$CFG` does not exist: create it containing only the new section with the absolute path.
4. If `$CFG` exists AND the `[mcp_servers.proton]` section is already there: rewrite just that section in place (preserving other sections and blank lines) so the `command` line points at `$PMCP_BIN`.
5. If `$CFG` exists AND the section is not present yet: append a leading blank line followed by the new section.

```bash
CFG="$HOME/.codex/config.toml"
PMCP_BIN="$(command -v proton-mcp)"
[ -n "$PMCP_BIN" ] || { echo "proton-mcp not on PATH — rerun Phase 3 first."; exit 1; }
mkdir -p "$(dirname "$CFG")"
test -f "$CFG" && cp "$CFG" "${CFG}.bak.$(date +%Y%m%d-%H%M%S)"

if [ -f "$CFG" ] && grep -q '^\[mcp_servers\.proton\]' "$CFG"; then
  # In-place replace: rewrite just the proton section. The awk script
  # emits all lines outside the section, replaces the section body with
  # a freshly-built version, and exits the section on either the next
  # [section] header OR a blank line (so the blank between sections is
  # preserved).
  TMP="$(mktemp)"
  awk -v cmd="$PMCP_BIN" '
    BEGIN { in_sec = 0 }
    /^\[mcp_servers\.proton\][[:space:]]*$/ {
      in_sec = 1
      print "[mcp_servers.proton]"
      print "command = \"" cmd "\""
      next
    }
    in_sec && /^\[/ { in_sec = 0 }
    in_sec && /^$/ { in_sec = 0 }
    !in_sec { print }
  ' "$CFG" > "$TMP" && mv "$TMP" "$CFG"
else
  {
    test -f "$CFG" && cat "$CFG"
    test -f "$CFG" && echo ""
    echo "[mcp_servers.proton]"
    echo "command = \"$PMCP_BIN\""
  } > "${CFG}.new"
  mv "${CFG}.new" "$CFG"
fi
```

### User-facing template

> "Now we tell Codex where to find this server. Codex has a config file at:
>
> `~/.codex/config.toml`
>
> I'm going to read what's already in it (so I don't disturb any other settings you have), add a `[mcp_servers.proton]` section with the absolute path to the server binary (`<PMCP_BIN>`), and write it back. I'll make a backup first."

After the write:

> "Done. Your config now includes the `proton` server pointing at `<PMCP_BIN>`. I backed up your previous config to `<backup-path>` just in case. Next we restart Codex and verify."

### Verification

```bash
grep -q '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml"
STORED_CMD="$(grep -A2 '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" \
  | sed -n 's/^command = "\(.*\)"$/\1/p' | head -1)"
[ -n "$STORED_CMD" ] && [ -x "$STORED_CMD" ]
```

All three checks must succeed.

### Failure

- **Existing config has malformed TOML:** Codex would have errored on startup if so, but if the agent's append corrupts something, the user has a `.bak` to roll back. Surface the issue, point at the backup, and stop.
- **Write permission denied:** Tell the user; check `~/.codex/` ownership.

### Exit ramp

None — this is the final modifying phase.

```

- [ ] **Step 5: Update Phase 6's user-facing template (restart instructions)**

**old_string:**

```
> "Two final steps.
>
> **Step 1: Fully quit Claude Desktop.** Cmd+Q (not just closing the window). Reopen.
>
> **Step 2: Test a tool call.** Try a prompt like:
>
> *"Use proton to search my `<your-label>` inbox for unread messages from this week."*
>
> If Claude calls a tool starting with `mail_` (you'll see it in the conversation), the install worked. Tell me what happens."
```

**new_string:**

```
> "Two final steps.
>
> **Step 1: Start a new Codex session.** If you currently have a `codex` session open, exit it (Ctrl+C / `exit`) and run `codex` again from a fresh terminal — Codex reads the config once at startup.
>
> **Step 2: Test a tool call.** Once the new session is running, try a prompt like:
>
> *"Use proton to search my `<your-label>` inbox for unread messages from this week."*
>
> If Codex calls a tool starting with `mail_` (you'll see it in the conversation), the install worked. Tell me what happens."
```

- [ ] **Step 6: Update Phase 6's "Tools don't appear" failure-mode item #4**

**old_string:**

```
3. Verify config:
   ```bash
   jq '.mcpServers["proton"]' \
     "$HOME/Library/Application Support/Claude/claude_desktop_config.json"
   ```
4. Check Claude Desktop's logs (Help → View Logs) for a startup error.
```

**new_string:**

```
3. Verify config:
   ```bash
   grep -A2 '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml"
   ```
4. Check Codex's session log (`~/.codex/log/` or `codex --debug`) for a startup error.
```

- [ ] **Step 7: Update the "You're done" closing line**

**old_string:**

```
> "All set. Your `proton-mcp` install is wired into Claude Desktop. A few useful follow-ups:
```

**new_string:**

```
> "All set. Your `proton-mcp` install is wired into Codex. A few useful follow-ups:
```

- [ ] **Step 8: Verify structural parity with `claude-desktop.md`**

```bash
cd /Users/bjunya/code/proton-mcp
grep -c '^## Phase ' agents/install/codex.md
grep -c '^### Sub-phase 1' agents/install/codex.md
```

Expected: phases = `7`, sub-phases = `4` (matches the proton-mcp Claude Desktop runbook, which has Phase 1 sub-phases 1a–1d — Bridge has fewer steps than GCP).

- [ ] **Step 9: Verify Codex-specific content is in place**

```bash
cd /Users/bjunya/code/proton-mcp
# Phase 0 detection check uses grep on TOML
grep -q "grep -q '\^\\\\\\[mcp_servers\\\\\\.proton\\\\\\]'" agents/install/codex.md && echo "phase 0 toml check: ok"

# Phase 5 references config.toml
grep -q '\.codex/config\.toml' agents/install/codex.md && echo "phase 5 toml path: ok"

# Phase 5 has the awk in-place rewrite
grep -q 'awk -v cmd=' agents/install/codex.md && echo "phase 5 awk pass: ok"

# Phase 6 references Codex session startup
grep -q 'Start a new Codex session' agents/install/codex.md && echo "phase 6 codex restart: ok"

# Closing line references Codex
grep -q 'wired into Codex\.' agents/install/codex.md && echo "closing codex: ok"

# No surviving Claude Desktop strings outside the historical/comparative
# contexts (there shouldn't be any — Bridge content doesn't mention Claude
# Desktop). This is a defense-in-depth check.
! grep -q 'Claude Desktop' agents/install/codex.md && echo "no claude desktop leftovers: ok"
```

Expected: all six lines print `ok`.

- [ ] **Step 10: Sanity-test the awk in-place rewrite logic**

Run a self-contained simulation to confirm the awk pass preserves other sections and replaces the proton section in place:

```bash
SCRATCH=$(mktemp -d)
CFG="$SCRATCH/config.toml"
cat > "$CFG" <<'TOML'
[other_section]
key = "value"

[mcp_servers.proton]
command = "/old/bare/name"

[mcp_servers.foo]
command = "/some/other/bin"
TOML

PMCP_BIN="/scratch/new/proton-mcp"
TMP="$(mktemp)"
awk -v cmd="$PMCP_BIN" '
  BEGIN { in_sec = 0 }
  /^\[mcp_servers\.proton\][[:space:]]*$/ {
    in_sec = 1
    print "[mcp_servers.proton]"
    print "command = \"" cmd "\""
    next
  }
  in_sec && /^\[/ { in_sec = 0 }
  in_sec && /^$/ { in_sec = 0 }
  !in_sec { print }
' "$CFG" > "$TMP" && mv "$TMP" "$CFG"

echo "--- result ---"
cat "$CFG"
echo "--- checks ---"
grep -q '^\[other_section\]' "$CFG" && echo "other_section preserved: ok"
grep -q '^\[mcp_servers\.foo\]' "$CFG" && echo "mcp_servers.foo preserved: ok"
grep -q '^command = "/scratch/new/proton-mcp"$' "$CFG" && echo "new command written: ok"
! grep -q '/old/bare/name' "$CFG" && echo "old command gone: ok"
rm -rf "$SCRATCH"
```

Expected output: the `--- result ---` block shows all three sections intact with the proton command updated to `/scratch/new/proton-mcp`; all four `: ok` lines print.

- [ ] **Step 11: Sanity-test the append-when-missing logic**

```bash
SCRATCH=$(mktemp -d)
CFG="$SCRATCH/config.toml"
cat > "$CFG" <<'TOML'
[other_section]
key = "value"
TOML

PMCP_BIN="/scratch/new/proton-mcp"
{
  cat "$CFG"
  echo ""
  echo "[mcp_servers.proton]"
  echo "command = \"$PMCP_BIN\""
} > "${CFG}.new"
mv "${CFG}.new" "$CFG"

echo "--- result ---"
cat "$CFG"
echo "--- checks ---"
grep -q '^\[other_section\]' "$CFG" && echo "other_section preserved: ok"
grep -q '^\[mcp_servers\.proton\]' "$CFG" && echo "proton section appended: ok"
grep -q '^command = "/scratch/new/proton-mcp"$' "$CFG" && echo "command written: ok"
rm -rf "$SCRATCH"
```

Expected output: the result block shows both sections separated by a blank line; all three `: ok` lines print.

- [ ] **Step 12: Commit**

```bash
cd /Users/bjunya/code/proton-mcp
git add agents/install/codex.md
git commit -m "$(cat <<'EOF'
docs: add Codex CLI install runbook

Mirrors agents/install/claude-desktop.md except for harness-specific
bits: Phase 0 check #6 looks at ~/.codex/config.toml; Phase 5 uses a
TOML append-or-replace with an awk-driven in-place rewrite when the
section already exists; Phase 6 references restarting `codex` rather
than Claude Desktop. Pattern lifted from multi-google-mcp's codex
runbook, adapted for the proton-mcp binary name and Bridge-based
Phase 1.

No test added — documentation-only change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Update the README to link to the new runbook

**Files:**
- Modify: `README.md` — single line in the "Quick install (let an agent do it)" section.

- [ ] **Step 1: Confirm the placeholder line is present**

```bash
cd /Users/bjunya/code/proton-mcp
grep -n 'Codex CLI.*coming in a follow-up' README.md
```

Expected: prints `41:- **Codex CLI** — coming in a follow-up.` (or wherever the line currently is — line 41 at time of writing).

- [ ] **Step 2: Replace the placeholder with the real link**

Use the `Edit` tool with:

**old_string:**

```
- **Codex CLI** — coming in a follow-up.
```

**new_string:**

```
- **Codex CLI** — [`agents/install/codex.md`](agents/install/codex.md)
```

- [ ] **Step 3: Verify the new bullet is in place and the linked file exists**

```bash
cd /Users/bjunya/code/proton-mcp
grep -n 'agents/install/codex\.md' README.md
test -f agents/install/codex.md
```

Expected: `grep` prints the new bullet line (and may also match the section's intro paragraph if it mentions the runbook). `test -f` succeeds.

- [ ] **Step 4: Verify both runbooks are linked from the README**

```bash
cd /Users/bjunya/code/proton-mcp
grep -c 'agents/install/[a-z-]*\.md' README.md
```

Expected: at least `2` matches (claude-desktop and codex).

- [ ] **Step 5: Commit**

```bash
cd /Users/bjunya/code/proton-mcp
git add README.md
git commit -m "$(cat <<'EOF'
docs: README links to the Codex CLI runbook

Replaces the "Codex CLI — coming in a follow-up." placeholder in the
"Quick install (let an agent do it)" section with a markdown link to
agents/install/codex.md, parallel to the existing Claude Desktop
link.

No test added — documentation-only change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: End-to-end sanity sweep of the new runbook

**Files:**
- No file changes expected — this is a read-only review pass. Only modify if issues are found.

- [ ] **Step 1: Read `codex.md` top to bottom**

Read the full file. Verify:

- Every section uses the named-blocks structure (Detection / Commands / User-facing template / Failure / Exit ramp) where applicable to that phase.
- No `TBD`, `TODO`, `<placeholder>`, or undefined references.
- Phase 5 uses TOML/grep/awk only — no leftover JSON/jq from Claude Desktop.
- Phase 6 references Codex (not Claude Desktop) throughout the user-facing template and failure modes.
- The closing "You're done" line says "Codex" (not "Claude Desktop").
- All shell commands have correct quoting for the `$HOME/.codex/config.toml` path (the path contains no spaces, so quoting is less critical than in the Claude Desktop runbook, but should still be defensive).

- [ ] **Step 2: Verify the file isn't accidentally identical to `claude-desktop.md`**

```bash
cd /Users/bjunya/code/proton-mcp
diff agents/install/claude-desktop.md agents/install/codex.md | head -30
```

Expected: a non-empty diff that touches the title, Phase 0 detection #6, Phase 0 user-facing bullet (split into two), Phase 5 entirely, Phase 6 restart instructions, Phase 6 failure mode #3/#4, and the closing line.

- [ ] **Step 3: Verify the runbook's own detection commands parse cleanly**

Run each detection block to confirm none of them have shell syntax errors. They may exit non-zero on this machine (depending on what's installed) — that's fine; we're testing the commands' well-formedness, not their results.

```bash
test -d "/Applications/Proton Mail Bridge.app" || test -d "$HOME/Applications/Proton Mail Bridge.app"; echo "phase 0 #1 exit: $?"
nc -z -G 2 127.0.0.1 1143 2>/dev/null; echo "phase 0 #2 exit: $?"
command -v uv >/dev/null; echo "phase 0 #3 exit: $?"
command -v proton-mcp >/dev/null && command -v proton-mcp-auth >/dev/null; echo "phase 0 #4 exit: $?"
find ~/.config/proton-mcp/accounts -maxdepth 1 -name '*.json' 2>/dev/null | head -1; echo "phase 0 #5 exit: $?"
grep -q '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" 2>/dev/null; echo "phase 0 #6 exit: $?"
```

Expected: each line prints `exit: <int>` — no `command not found`, no syntax error from any shell.

- [ ] **Step 4: Run repo-wide lint and test checks**

This repo has `pyproject.toml` with `ruff`, `pytest`, and `mypy` configured. Run them from the repo root:

```bash
cd /Users/bjunya/code/proton-mcp
uv run ruff check .
uv run mypy
uv run pytest
```

Expected: ruff, mypy, pytest all pass. Markdown-only changes shouldn't affect any of these. If any fail, the failure is unrelated to this PR — surface it and stop.

- [ ] **Step 5: If any issue found in steps 1–4, fix it as a separate commit**

If a fix is needed:

```bash
cd /Users/bjunya/code/proton-mcp
git add <files>
git commit -m "$(cat <<'EOF'
docs: <one-line description of the fix>

<short body explaining what was wrong and how the fix addresses it>

No test added — documentation-only change.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

If no fix is needed, this task ends without a commit.

---

## Self-review checklist

After completing all tasks, before pushing the branch:

- [ ] `agents/install/codex.md` has 7 phases (0–6).
- [ ] Phase 1 in `codex.md` has 4 sub-phases (1a–1d) — matches `claude-desktop.md`.
- [ ] Phase 5 uses TOML grep + awk append-or-replace (no JSON merge text left over).
- [ ] Phase 5 backs up the config before writing.
- [ ] Phase 5 explicitly preserves existing entries.
- [ ] Phase 5 resolves the absolute path of `proton-mcp` at write time.
- [ ] Phase 6 says "Start a new Codex session" and references `mail_*` tools.
- [ ] The closing "You're done" line says "Codex."
- [ ] README's "Quick install" section links to both `claude-desktop.md` and `codex.md`.
- [ ] All commit messages say "No test added — documentation-only change."
- [ ] `ruff` / `mypy` / `pytest` all pass on the branch.

---

## Out-of-band considerations for `/code-task`

- **Phase 3 (pre-push verification):** `ruff` / `mypy` / `pytest` are configured. None of this PR's changes touch Python, so they should pass untouched. If they fail on `main` already, the failure is unrelated to this PR — surface it and stop, per `/code-task` Phase 3.2.
- **Phase 4 (PR body):** Title = "Codex CLI install runbook". Summary bullets: (1) new `agents/install/codex.md` mirroring the Claude Desktop runbook with TOML config wiring in Phase 5; (2) README placeholder line replaced with a real link.
- **Phase 5 (Aria review):** Aria's likely areas of feedback — correctness of the awk in-place rewrite (does it really preserve adjacent blank lines and other sections?), absence of Claude-Desktop residue (any leftover JSON references would be a regression), and whether Phase 0 check #6 is robust against an unrelated `[mcp_servers.protonsomething]` typo (it shouldn't match because the regex uses `\.proton\]` end-anchor).
- **Phase 6 (merge):** Per the `--merge` flag passed to `/code-task`, auto-merge after Aria approves.
- **Phase 7 (notify):** Standard `/aria:notify` "Pull Request Merged!" message.
