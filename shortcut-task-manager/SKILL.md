---
name: shortcut-task-manager
description: Interact with Shortcut to search, inspect, create, update, label, comment on, and organize stories and epics using API-driven workflows. Use when a user asks to manage Shortcut work items, inspect workflow states, map members or custom fields, or operate on Shortcut similarly to Linear workflows.
---

# Shortcut Task Manager

Use this skill for general-purpose Shortcut operations.

Keep this skill Shortcut-generic. Put spreadsheet-specific or domain-specific import rules in separate recipe files outside the base skill.

## Quick Start

1. Configure credentials in the skill directory:
- `SHORTCUT_API_TOKEN` required
- `SHORTCUT_API_BASE_URL` optional, defaults to `https://api.app.shortcut.com/api/v3`

2. Use this skill in one of two ways:
- Codex skill mode through `SKILL.md`
- MCP-style stdio through `scripts/shortcut_mcp_server.py`

3. Prefer read-first workflows before writes.

## Core Workflow

1. Resolve intent:
- read operations: search, inspect, list, lookup
- write operations: create, update, label, comment, assign

2. Resolve IDs before writes:
- story IDs
- workflow state IDs
- custom field IDs and enum value IDs
- group/team IDs if applicable

3. Execute explicit writes only:
- send only fields requested by the user
- avoid inferred destructive operations
- fail gracefully if a requested team/group cannot be created or found
- for enum custom fields, prefer name-based helpers so the script resolves `value_id` correctly

4. Report outcomes clearly:
- include object IDs and URLs when available
- include changed fields
- surface API errors with enough detail to debug

## Command Patterns

```bash
# Create local env file
cp .env.example .env

# Validate auth
python3 scripts/shortcut.py me

# Search and inspect
python3 scripts/shortcut.py search-stories --query "payment retry bug" --limit 10
python3 scripts/shortcut.py search-epics --query "platform hardening" --limit 10
python3 scripts/shortcut.py list-stories --limit 25 --sort state
python3 scripts/shortcut.py list-stories --epic-id 1234
python3 scripts/shortcut.py list-epics --active --sort points
python3 scripts/shortcut.py list-files --story-id 1234
python3 scripts/shortcut.py list-linked-files --story-id 1234
python3 scripts/shortcut.py get-story --story-id 1234
python3 scripts/shortcut.py download-file --file-public-id FILE_PUBLIC_ID --output ./attachment.png
python3 scripts/shortcut.py weekly-report --timezone Pacific/Auckland
python3 scripts/shortcut.py weekly-report --timezone Pacific/Auckland --output /tmp/acme-weekly-report.md --pdf-output /tmp/acme-weekly-report.pdf

# Use raw JSON for scripting
python3 scripts/shortcut.py search-stories --query "payment retry bug" --limit 10 --json
python3 scripts/shortcut.py search-epics --query "platform hardening" --limit 10 --json
python3 scripts/shortcut.py list-epics --json

# Set a custom field by names, without looking up UUIDs
python3 scripts/shortcut.py set-story-custom-field \
  --story-id 1234 \
  --field-name "Priority" \
  --value-name "High"

# Create or update using names instead of IDs
python3 scripts/shortcut.py create-story \
  --name "Investigate retry policy" \
  --workflow-state-name "Backlog" \
  --group-name "Platform" \
  --epic-name "Retry Hardening"

python3 scripts/shortcut.py update-story \
  --story-id 1234 \
  --workflow-state-name "To Do" \
  --field-name "Priority" \
  --value-name "High"

# Preview a bulk update before applying it
python3 scripts/shortcut.py bulk-update-stories \
  --query "label:backend" \
  --workflow-state-name "To Do" \
  --dry-run

# Rank the next items to work on
python3 scripts/shortcut.py next-stories --limit 10 --exclude-subtasks

# Find stories that need refinement
python3 scripts/shortcut.py refinement-list --limit 10

# Owner IDs in some workspaces are UUID strings, so owner names are usually safer
python3 scripts/shortcut.py update-story \
  --story-id 1234 \
  --owner-names "Jane Doe"

# Assign a story to the authenticated Shortcut user
python3 scripts/shortcut.py update-story \
  --story-id 1234 \
  --owner-self

# Discover workspace metadata
python3 scripts/shortcut.py list-projects
python3 scripts/shortcut.py list-groups
python3 scripts/shortcut.py ensure-group --name "Web" --mention-name "web"
python3 scripts/shortcut.py list-workflows
python3 scripts/shortcut.py list-members
python3 scripts/shortcut.py list-labels
python3 scripts/shortcut.py list-custom-fields
python3 scripts/shortcut.py get-custom-field --custom-field-id "custom-field-uuid"

# Story operations
python3 scripts/shortcut.py create-story \
  --name "Investigate retry backoff" \
  --workflow-state-id 500000123

python3 scripts/shortcut.py update-story \
  --story-id 1234 \
  --workflow-state-id 500000456

python3 scripts/shortcut.py set-story-custom-fields \
  --story-id 1234 \
  --custom-fields '[{"field_id":"custom-field-uuid","value_id":"enum-value-uuid"}]'

python3 scripts/shortcut.py update-story-labels \
  --story-id 1234 \
  --labels '[{"name":"Customer Escalation"}]'

python3 scripts/shortcut.py upload-file \
  --path ./diagram.png \
  --story-id 1234

python3 scripts/shortcut.py create-linked-file \
  --name "Design Spec" \
  --url "https://example.com/spec" \
  --story-id 1234

python3 scripts/shortcut.py comment-story \
  --story-id 1234 \
  --text "Shipped to staging; monitoring for 24h."

# Epic operations
python3 scripts/shortcut.py create-epic --name "Retry Hardening"
python3 scripts/shortcut.py update-epic --epic-id 1234 --description "Tighten backoff and rate-limit handling."
python3 scripts/shortcut.py update-epic-labels --epic-id 1234 --labels '[{"name":"Platform"}]'
```

Custom field note:
- Enum custom fields in Shortcut expect `value_id`, not `value`.
- The safest path is `set-story-custom-field --field-name ... --value-name ...` because the helper resolves the correct enum `value_id` automatically.

File note:
- `download-file` resolves Shortcut file metadata and attempts a direct binary download.
- Some Shortcut media URLs may still reject API-token access and require a logged-in browser session cookie.
- In that case, `download-file` returns a structured `download_blocked` result with the media URL instead of failing generically.

Reporting note:
- `weekly-report` generates a markdown report with Monday-based resolved-week groupings, assignees, and date-only table columns.
- By default it derives the report slug from the Shortcut workspace metadata and writes to `/tmp/<workspace-slug>-weekly-report-YYYY-MM-DD.md`; override with `--output` or `--report-slug`.
- Pass `--tex-output /path/to/report.tex` and `--pdf-output /path/to/report.pdf` to export a LaTeX `longtable` report and a XeLaTeX-rendered PDF.
- For wide tabular exports, do not rely on Pandoc’s default Markdown table conversion.
- Prefer normalized Shortcut data -> explicit LaTeX `longtable` -> `xelatex`.
- Use A4 landscape when more than 6 columns are required.
- Verify generated PDFs with `pdftotext` when possible.

Permissions note:
- The skill cannot bypass Codex sandbox/network policy by itself.
- The practical fix is a one-time approval for the Shortcut CLI prefix, for example `python3 scripts/shortcut.py`, so common skill commands can reuse that approval.

Known workspace quirks:
- owner IDs may be UUID strings rather than integers
- owner names are usually safer than raw owner IDs
- member mention names may live under `profile.mention_name`
- enum custom fields require `value_id`

## Safety Rules

- Validate IDs before writes.
- Prefer `group_id` over `project_id` where Shortcut expects team/group ownership.
- Stop and ask if duplicate active epics share the same name and the next step is ambiguous.
- Avoid bulk changes unless the user explicitly requests them.
- If a field is unknown, inspect the current object or workspace metadata before writing.

## References

- General Shortcut reference: `references/shortcut-api-cheatsheet.md`
- Public skill metadata: `agents/openai.yaml`
- Generic CLI helper: `scripts/shortcut.py`
- MCP server: `scripts/shortcut_mcp_server.py`

## Recipes

Recipe-specific imports and mappings should live outside the base skill, for example under `recipes/`.
