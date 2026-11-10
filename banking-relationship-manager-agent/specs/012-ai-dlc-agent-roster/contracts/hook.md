# Hook Contract

`.github/hooks/speckit-guard.json` registers a `preToolUse` command hook that runs `scripts/speckit_guard.py` (bash and powershell entries).

**Input**: the hook JSON payload on stdin. The script searches the tool name and arguments for command text and file paths, tolerating different key spellings.

**Deny** (stdout `{"permissionDecision": "deny", "permissionDecisionReason": "..."}`) when the tool call:
- runs `speckit_flow gate approve|reject` or `speckit_flow rules approve|discard`, or
- writes to `audit.jsonl`, `state.json`, `state.md`, `rules.json`, or review JSON under `reviews/`, via an edit tool or shell redirection.

**Allow** otherwise (stdout `{"permissionDecision": "allow"}`), including read-only `status`, `review save`, `rules propose`, `stage start|done`. Unparseable input allows, because the CLI refuses non-human actors itself.

The hook only applies to agent sessions; a human running the CLI in a terminal is unaffected.
