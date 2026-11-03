# Contributing

Thanks for helping improve this skill.

## Reporting an issue

Client updates regularly change the WorkBuddy login-state format, which can break
token extraction. When something stops working, please open an issue with:

- WorkBuddy client version (`帮助 → 关于`),
- OS and Python/Node versions,
- the **exact** error output (you may redact tokens — but keep the error code
  and message shape, e.g. `code=12153 invalid_grant`),
- which step failed: `extract` / `checkin` / `status` / `run` / `cloud_guard`.

**Never paste a real token, an AirScript-Token, or your sheet URL** into an issue.

## Development

The skill lives in two places:

| Path | Purpose |
|---|---|
| `~/.workbuddy/skills/workbuddy-checkin/` | the installed copy the agent actually runs |
| this repository | the source of truth for distribution |

Sync changes from the installed copy into the repo, and make sure you run the
sanity sweep below before committing.

### Before committing — mandatory sanity sweep

```bash
# 1. remove runtime artifacts (they contain plaintext tokens)
rm -rf scripts/out scripts/plan.json scripts/deploy

# 2. reset credentials to the empty template
cat > scripts/kdocs_config.json <<'JSON'
{
  "_说明": "首次使用请填入自己的凭据；也可用环境变量 KDOCS_FILE_ID / KDOCS_SCRIPT_ID / KDOCS_TOKEN 覆盖",
  "file_id": "", "script_id": "", "token": "", "table_url": "",
  "worksheet_id": 0, "sheet_name": ""
}
JSON

# 3. scan for leaks — patterns only, never paste a real token here
grep -rE "eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\." . && echo "LEAK: JWT"
grep -rE '"token"[[:space:]]*:[[:space:]]*"[A-Za-z0-9]{16,}"' . && echo "LEAK: token"

# 4. syntax + functional check
for f in scripts/*.py; do python3 -c "import ast;ast.parse(open('$f',encoding='utf-8').read())"; done
node --check scripts/decrypt_envelope.js
node --check assets/workbuddy-checkin-cloud.airscript.js
python3 scripts/wb_checkin.py auto
```

Step 4's `wb_checkin.py auto` performs a **real** check-in against the live API.
Use it to confirm nothing broke, but never commit the resulting `scripts/out/`.

## Conventions

- **Chinese comments/docstrings** for consistency with the rest of the codebase;
  user-facing docs exist in both Chinese (`README.md`) and English (`README.en.md`).
- **Zero third-party dependencies** — Python standard library plus Node's built-in
  `crypto` only. This keeps the skill installable anywhere.
- **Never log secrets.** Report token *lengths*, never token *contents*.
- **Keep `keyId` validation.** Process memory contains base64 decoys; validating
  `sha256(sha256(secret))[:16]` against the envelope is what makes extraction
  reliable.
- **Prefer Node for crypto.** Windows CNG via `ctypes` is a trap
  (`0xC00000BB` / `0xC0000023`).

## Areas that would love help

- **macOS/Linux support** — a Linux `/proc/<pid>/mem` implementation of the
  memory scanner, so the skill stops being Windows-only.
- **A one-command installer** that creates the sheet, deploys the AirScript and
  writes `kdocs_config.json` end to end.
- **Push-based self-healing** — currently the guard polls the sheet; a webhook
  (`dbsheet.create_webhook` exists) could notify the client the moment a check-in
  fails, instead of waiting for the next scheduled poll.
- **More notification channels** — the AirScript currently supports Bark and
  generic webhooks.
