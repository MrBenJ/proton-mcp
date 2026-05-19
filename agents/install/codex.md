# Install `proton-mcp` into Codex CLI — Agent Runbook

> **Audience:** You are an AI agent (Codex CLI, Claude Code, Cursor, etc.) running locally inside a clone of the `proton-mcp` repo. The human in front of you has asked you to install this server. Follow this runbook end-to-end. The user may have little or no experience with the command line or TOML — be patient.

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

# 6. proton server already wired into Codex config
grep -q '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml" 2>/dev/null
```

### User-facing template

> "Let me look at what's already in place — one moment.
>
> - [✓/✗] Proton Mail Bridge installed
> - [✓/✗] Bridge IMAP reachable at 127.0.0.1:1143
> - [✓/✗] `uv` installed
> - [✓/✗] `proton-mcp` CLI installed
> - [✓/✗] At least one Proton account connected
> - [✓/✗] `proton` server wired into Codex (`~/.codex/config.toml`)
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
> - `proton-mcp` — the server itself (Codex will start it)
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
> I'm going to read what's already in it (so I don't disturb any other settings you have), add a `[mcp_servers.proton]` section with the absolute path to the server binary, and write it back. I'll make a backup first."

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

---

## Phase 6 — Verify and restart

### User-facing template

> "Two final steps.
>
> **Step 1: Start a new Codex session.** If you currently have a `codex` session open, exit it (Ctrl+C / `exit`) and run `codex` again from a fresh terminal — Codex reads the config once at startup.
>
> **Step 2: Test a tool call.** Once the new session is running, try a prompt like:
>
> *"Use proton to search my `<your-label>` inbox for unread messages from this week."*
>
> If Codex calls a tool starting with `mail_` (you'll see it in the conversation), the install worked. Tell me what happens."

### Failure modes

**Tools don't appear:**

1. Confirm the user started a brand-new `codex` session (not just resumed an existing one).
2. Run `proton-mcp` manually:
   ```bash
   proton-mcp
   ```
   Should print nothing and wait on stdin (Ctrl-C to exit). If it errors, surface the message — likely a credentials issue.
3. Verify config:
   ```bash
   grep -A2 '^\[mcp_servers\.proton\]' "$HOME/.codex/config.toml"
   ```
4. Check Codex's session log (`~/.codex/log/` or `codex --debug`) for a startup error.

**`error: cannot reach Bridge at 127.0.0.1:1143`:**

Bridge isn't running. Open the Bridge app. (And consider asking the user whether they want Bridge to launch at login — they'd set that in Bridge's Settings.)

**`error: Bridge TLS fingerprint ... does not match`:**

Bridge regenerated its certificate. Have them rerun `proton-mcp-auth add <label>` to re-pin.

---

## You're done

When Phase 6 succeeds, tell the user:

> "All set. Your `proton-mcp` install is wired into Codex. A few useful follow-ups:
>
> - **Add another account:** `proton-mcp-auth add <new-label>`
> - **List configured accounts:** `proton-mcp-auth list`
> - **Remove an account:** `proton-mcp-auth remove <label>`
> - **Revalidate after a Bridge reset:** `proton-mcp-auth test <label>`
> - **Troubleshooting:** see the project README.
>
> Happy to help if anything goes sideways later."
