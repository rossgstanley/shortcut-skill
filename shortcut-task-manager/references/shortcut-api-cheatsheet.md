# Shortcut API Cheatsheet

Use this file as quick reference for common operations supported by `scripts/shortcut.py`.

## Environment

- `SHORTCUT_API_TOKEN`: API token used in `Shortcut-Token` header.
- `SHORTCUT_API_BASE_URL`: Optional override, default `https://api.app.shortcut.com/api/v3`.
- The CLI loads `.env` automatically from the current working directory, `scripts/`, or the skill root.

## Core Endpoints

- `GET /member`: Validate token and identify caller.
- `GET /search/stories?query=...`: Search stories by text query.
- `GET /stories/{story_id}`: Fetch a story.
- `GET /projects`: List projects.
- `GET /workflows`: List workflows and their state IDs.
- `GET /members`: List members and IDs.
- `GET /labels`: List labels and IDs.
- `GET /files`: List uploaded files.
- `GET /files/{file_public_id}`: Get one uploaded file.
- `POST /files`: Upload a file or image using multipart form data.
- `GET /linked-files`: List linked files.
- `GET /linked-files/{linked_file_id}`: Get one linked file.
- `POST /linked-files`: Create a linked external file.
- `POST /stories`: Create a story.
- `PUT /stories/{story_id}`: Update story fields.
- `POST /stories/{story_id}/comments`: Add a comment.

## Common Story Fields

- `name`: Story title.
- `description`: Markdown description.
- `project_id`: Numeric project ID.
- `workflow_state_id`: Numeric workflow state ID.
- `owner_ids`: Array of member IDs.
- `label_ids`: Array of label IDs.
- `estimate`: Story estimate.
- `story_type`: `feature`, `bug`, or `chore`.

## Practical Usage Notes

- Prefer targeted updates: send only fields that should change.
- Resolve IDs first by querying projects/workflows through your existing Shortcut process or API exploration.
- This workspace/API version rejects `GET /stories`; use state-based search to enumerate stories.
- When unsure of writable fields, fetch the story and mirror key names from existing payload structure.
- For MCP integration, run `scripts/shortcut_mcp_server.py` and expose it as a stdio server in your client configuration.
- `list-stories` prints a table by default; pass `--json` for raw payloads.
- For enum custom fields, Shortcut expects `value_id`, not `value`.
- Uploaded files can be attached to a story with `story_id`; linked files are external URLs.
