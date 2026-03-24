# Shortcut Skill For Codex

This repository contains a reusable Codex skill for working with Shortcut.

The public, shareable part of the repo is:

```text
shortcut-task-manager/
```

That folder contains the general-purpose skill, helper CLI, MCP server, and setup metadata.

## What It Does

The skill supports common Shortcut workflows such as:

- searching stories
- listing stories, epics, workflows, members, labels, groups, and custom fields
- creating and updating stories
- creating and updating epics
- adding comments
- uploading files and images
- creating linked files
- setting labels
- setting custom fields
- resolving team/group IDs for writes

For enum custom fields such as `Priority`, the safe path is to set them by field name and value name through the helper, which resolves Shortcut's required `value_id` shape automatically.

Common workspace quirks this skill handles:
- owner IDs may be UUID strings rather than integers
- owner names are often safer than raw owner IDs
- member mention names may be nested under `profile.mention_name`
- enum custom fields require `value_id`

## Repository Layout

```text
shortcut-task-manager/
  SKILL.md
  .env.example
  agents/
    openai.yaml
  references/
    shortcut-api-cheatsheet.md
  scripts/
    shortcut.py
    shortcut_mcp_server.py
```

Optional local recipe or migration files should live outside the generic skill surface. They do not need to be part of the public repository.

## Architecture

This repo has three layers:

- CLI: [shortcut.py](/Users/rossstanley/dev/shortcut-skill/shortcut-task-manager/scripts/shortcut.py) contains the core Shortcut API logic and can be run directly from the terminal.
- Skill: [SKILL.md](/Users/rossstanley/dev/shortcut-skill/shortcut-task-manager/SKILL.md) tells Codex how to use the CLI and what workflows to prefer.
- MCP server: [shortcut_mcp_server.py](/Users/rossstanley/dev/shortcut-skill/shortcut-task-manager/scripts/shortcut_mcp_server.py) exposes the same core operations to MCP-compatible clients over stdio.

In practice:

- use the CLI when you want direct scripted or terminal access
- use the skill when you want to prompt Codex in natural language
- use the MCP server when an MCP client such as Claude Desktop or Cursor needs to call the same operations as tools

The CLI is the source of truth for behavior. The skill and MCP server are adapters around it.

## Install

Clone the repo, then install the skill into your Codex skills directory:

```bash
mkdir -p ~/.codex/skills
ln -s "$(pwd)/shortcut-task-manager" ~/.codex/skills/shortcut-task-manager
```

Restart Codex after creating the symlink.

## Credentials

Users should place their Shortcut API token in:

```text
shortcut-task-manager/.env
```

Start from the committed template:

```bash
cp shortcut-task-manager/.env.example shortcut-task-manager/.env
```

Example:

```dotenv
SHORTCUT_API_TOKEN=your-token-here
SHORTCUT_API_BASE_URL=https://api.app.shortcut.com/api/v3
```

Commit:

- `.env.example`

Do not commit:

- `.env`

## Usage

Once installed, prompt Codex with:

```text
Use $shortcut-task-manager to list Shortcut stories.
Use $shortcut-task-manager to create a story in Backlog.
Use $shortcut-task-manager to inspect custom fields in Shortcut.
```

Useful CLI patterns:

Assign a story to yourself:

```bash
python3 shortcut-task-manager/scripts/shortcut.py update-story \
  --story-id 1234 \
  --owner-self
```

Set a story priority safely:

```bash
python3 shortcut-task-manager/scripts/shortcut.py set-story-custom-field \
  --story-id 1234 \
  --field-name "Priority" \
  --value-name "High"
```

Validate a story update without writing it:

```bash
python3 shortcut-task-manager/scripts/shortcut.py validate-story-update \
  --story-id 1234 \
  --owner-self \
  --field-name "Priority" \
  --value-name "High"
```

Bulk enrich stories from a plan:

```bash
python3 shortcut-task-manager/scripts/shortcut.py bulk-update-stories \
  --query "label:needs-triage" \
  --workflow-state-name "Backlog" \
  --owner-self \
  --field-name "Priority" \
  --value-name "Medium" \
  --story-type feature \
  --dry-run
```

Then rerun with `--yes` to apply the batch.

Upload an image to a story:

```bash
python3 shortcut-task-manager/scripts/shortcut.py upload-file \
  --path ./diagram.png \
  --story-id 1234
```

Download an uploaded file from Shortcut:

```bash
python3 shortcut-task-manager/scripts/shortcut.py download-file \
  --file-public-id FILE_PUBLIC_ID \
  --output ./attachment.png
```

Note:
- some Shortcut media URLs may reject API-token access and require a logged-in browser session cookie
- in that case `download-file` returns a structured `download_blocked` result with the file metadata and media URL instead of writing the binary to disk

Create a linked external file on a story:

```bash
python3 shortcut-task-manager/scripts/shortcut.py create-linked-file \
  --name "Design Spec" \
  --url "https://example.com/spec" \
  --story-id 1234
```

## MCP

If you want to run the local MCP-compatible server, use:

```bash
python3 shortcut-task-manager/scripts/shortcut_mcp_server.py
```

Configure your MCP client to launch that script with the working directory set to `shortcut-task-manager/`.

## Claude Desktop

You can configure this skill's MCP server in Claude Desktop with a custom server entry such as `shortcut-custom`.

Example:

```json
{
  "mcpServers": {
    "shortcut-custom": {
      "command": "python3",
      "args": [
        "/absolute/path/to/shortcut-skill/shortcut-task-manager/scripts/shortcut_mcp_server.py"
      ],
      "cwd": "/absolute/path/to/shortcut-skill/shortcut-task-manager",
      "env": {
        "SHORTCUT_API_TOKEN": "paste-your-token-here",
        "SHORTCUT_API_BASE_URL": "https://api.app.shortcut.com/api/v3"
      }
    }
  }
}
```

Notes:

- `shortcut-custom` is just an example server name. Any distinct name is fine.
- Users can put `SHORTCUT_API_TOKEN` either in Claude Desktop's `env` block or in `shortcut-task-manager/.env`.
- `cwd` should be the skill root, not `scripts/`.
- `shortcut.py` does not need to be moved. Python resolves `import shortcut` from the directory of `shortcut_mcp_server.py`, which is already `shortcut-task-manager/scripts/`.
- If a user already has the official Shortcut MCP configured, they should use a distinct name such as `shortcut-custom` to avoid confusion.

An example config file is included at:

- `examples/claude_desktop_config.example.json`

## Files To Look At

- `shortcut-task-manager/SKILL.md`
- `shortcut-task-manager/agents/openai.yaml`
- `shortcut-task-manager/references/shortcut-api-cheatsheet.md`
- `shortcut-task-manager/scripts/shortcut.py`
- `shortcut-task-manager/scripts/shortcut_mcp_server.py`
- `examples/claude_desktop_config.example.json`

## Publishing Checklist

Before publishing:

1. keep `.env` ignored
2. keep `.DS_Store` ignored
3. remove any local absolute paths from docs
4. keep recipe-specific or customer-specific workflows out of the generic skill folder
