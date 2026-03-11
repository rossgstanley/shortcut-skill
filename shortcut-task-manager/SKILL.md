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
python3 scripts/shortcut.py list-stories --limit 25
python3 scripts/shortcut.py get-story --story-id 1234

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

python3 scripts/shortcut.py comment-story \
  --story-id 1234 \
  --text "Shipped to staging; monitoring for 24h."

# Epic operations
python3 scripts/shortcut.py create-epic --name "Retry Hardening"
python3 scripts/shortcut.py update-epic --epic-id 1234 --description "Tighten backoff and rate-limit handling."
python3 scripts/shortcut.py update-epic-labels --epic-id 1234 --labels '[{"name":"Platform"}]'
```

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
