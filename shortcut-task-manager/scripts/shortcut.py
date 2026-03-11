#!/usr/bin/env python3
"""Minimal Shortcut API CLI for day-to-day story operations."""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional


DEFAULT_BASE_URL = "https://api.app.shortcut.com/api/v3"


def load_dotenv() -> None:
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(script_dir, ".env"),
        os.path.join(os.path.dirname(script_dir), ".env"),
    ]

    for path in candidates:
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


def build_url(path: str, query: Optional[Dict[str, str]] = None) -> str:
    base = os.environ.get("SHORTCUT_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    cleaned = path if path.startswith("/") else f"/{path}"
    url = f"{base}{cleaned}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    return url


def request(
    method: str,
    path: str,
    data: Optional[dict] = None,
    query: Optional[Dict[str, str]] = None,
) -> dict:
    token = os.environ.get("SHORTCUT_API_TOKEN")
    if not token:
        raise RuntimeError("Missing SHORTCUT_API_TOKEN environment variable")

    body = None
    headers = {
        "Shortcut-Token": token,
        "Accept": "application/json",
    }

    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url=build_url(path, query=query),
        data=body,
        headers=headers,
        method=method.upper(),
    )

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as err:
        payload = err.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Shortcut API error {err.code}: {payload}") from err


def search_stories(query: str, limit: int) -> dict:
    return request("GET", "/search/stories", query={"query": query, "page_size": str(limit)})


def parse_json_arg(raw: Optional[str], field_name: str):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON for {field_name}: {err.msg}") from err


def format_story_table(payload: dict) -> str:
    stories = payload.get("data", [])
    if not stories:
        return "No stories found."

    columns = [
        ("ID", lambda story: str(story.get("id", ""))),
        ("Name", lambda story: story.get("name", "")),
        ("Type", lambda story: story.get("story_type", "")),
        ("State", lambda story: story.get("workflow_state_name", str(story.get("workflow_state_id", "")))),
        ("Estimate", lambda story: "" if story.get("estimate") is None else str(story.get("estimate"))),
        ("URL", lambda story: story.get("app_url", "")),
    ]

    widths = []
    for header, getter in columns:
        max_width = len(header)
        for story in stories:
            max_width = max(max_width, len(getter(story)))
        widths.append(max_width)

    lines = []
    header_row = "  ".join(header.ljust(widths[index]) for index, (header, _) in enumerate(columns))
    divider = "  ".join("-" * widths[index] for index in range(len(columns)))
    lines.append(header_row)
    lines.append(divider)

    for story in stories:
        row = "  ".join(
            getter(story).ljust(widths[index]) for index, (_, getter) in enumerate(columns)
        )
        lines.append(row)

    return "\n".join(lines)


def cmd_me(_: argparse.Namespace) -> dict:
    return request("GET", "/member")


def cmd_search_stories(args: argparse.Namespace) -> dict:
    return search_stories(args.query, args.limit)


def cmd_list_stories(args: argparse.Namespace) -> dict:
    if args.project_id is not None:
        raise RuntimeError("Project filtering is not supported by list-stories yet")

    workflows = cmd_list_workflows(argparse.Namespace())
    state_names = {}
    states = []
    for workflow in workflows:
        for state in workflow.get("states", []):
            state_names[state["id"]] = state["name"]
            if args.workflow_state_id is not None and state.get("id") != args.workflow_state_id:
                continue
            if state.get("num_stories", 0) > 0:
                states.append(state)

    stories = []
    seen_story_ids = set()
    for state in states:
        result = search_stories('state:"{0}"'.format(state["name"]), args.limit)
        for story in result.get("data", []):
            story_id = story.get("id")
            if story_id in seen_story_ids:
                continue
            seen_story_ids.add(story_id)
            story["workflow_state_name"] = state_names.get(story.get("workflow_state_id"), "")
            stories.append(story)
            if len(stories) >= args.limit:
                return {"data": stories, "next": None, "total": len(stories)}

    return {"data": stories, "next": None, "total": len(stories)}


def cmd_get_story(args: argparse.Namespace) -> dict:
    return request("GET", f"/stories/{args.story_id}")


def cmd_list_projects(_: argparse.Namespace) -> dict:
    return request("GET", "/projects")


def cmd_list_groups(_: argparse.Namespace) -> dict:
    return request("GET", "/groups")


def cmd_create_group(args: argparse.Namespace) -> dict:
    payload = {
        "name": args.name,
        "mention_name": args.mention_name,
    }
    if args.description is not None:
        payload["description"] = args.description
    if args.color is not None:
        payload["color"] = args.color
    if args.color_key is not None:
        payload["color_key"] = args.color_key
    if args.member_ids:
        payload["member_ids"] = args.member_ids
    workflow_ids = args.workflow_ids
    if not workflow_ids:
        workflows = cmd_list_workflows(argparse.Namespace())
        workflow_ids = [workflow["id"] for workflow in workflows]
    if not workflow_ids:
        raise RuntimeError("No workflow IDs available for group creation")
    payload["workflow_ids"] = workflow_ids
    return request("POST", "/groups", data=payload)


def cmd_ensure_group(args: argparse.Namespace) -> dict:
    groups = cmd_list_groups(argparse.Namespace())
    existing = next((group for group in groups if group.get("name") == args.name), None)
    if existing is not None:
        return existing
    return cmd_create_group(args)


def cmd_create_project(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    if args.description is not None:
        payload["description"] = args.description
    return request("POST", "/projects", data=payload)


def cmd_list_workflows(_: argparse.Namespace) -> dict:
    return request("GET", "/workflows")


def cmd_list_epics(_: argparse.Namespace) -> dict:
    return request("GET", "/epics")


def cmd_create_epic(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    if args.description is not None:
        payload["description"] = args.description
    if args.project_ids:
        payload["project_ids"] = args.project_ids
    if args.group_id is not None:
        payload["group_id"] = args.group_id
    if args.owner_ids:
        payload["owner_ids"] = args.owner_ids
    if args.label_ids:
        payload["label_ids"] = args.label_ids
    return request("POST", "/epics", data=payload)


def cmd_update_epic(args: argparse.Namespace) -> dict:
    payload = {}
    if args.name is not None:
        payload["name"] = args.name
    if args.description is not None:
        payload["description"] = args.description
    if getattr(args, "archived", None) is not None:
        payload["archived"] = args.archived
    if args.project_ids is not None:
        payload["project_ids"] = args.project_ids
    if args.group_id is not None:
        payload["group_id"] = args.group_id
    if args.owner_ids is not None:
        payload["owner_ids"] = args.owner_ids
    labels = parse_json_arg(args.labels, "labels")
    if labels is not None:
        payload["labels"] = labels
    if not payload:
        raise RuntimeError("No epic update fields provided")
    return request("PUT", f"/epics/{args.epic_id}", data=payload)


def cmd_list_members(_: argparse.Namespace) -> dict:
    return request("GET", "/members")


def cmd_list_labels(_: argparse.Namespace) -> dict:
    return request("GET", "/labels")


def cmd_list_custom_fields(_: argparse.Namespace) -> dict:
    return request("GET", "/custom-fields")


def cmd_get_custom_field(args: argparse.Namespace) -> dict:
    return request("GET", f"/custom-fields/{args.custom_field_id}")


def cmd_create_label(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    if args.color is not None:
        payload["color"] = args.color
    if args.description is not None:
        payload["description"] = args.description
    return request("POST", "/labels", data=payload)


def cmd_create_story(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    optional_fields = {
        "description": args.description,
        "workflow_state_id": args.workflow_state_id,
        "estimate": args.estimate,
        "story_type": args.story_type,
        "project_id": args.project_id,
        "epic_id": args.epic_id,
        "group_id": args.group_id,
        "parent_story_id": args.parent_story_id,
        "source_task_id": args.source_task_id,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    if args.owner_ids:
        payload["owner_ids"] = args.owner_ids
    labels = parse_json_arg(args.labels, "labels")
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    if labels is not None:
        payload["labels"] = labels
    if custom_fields is not None:
        payload["custom_fields"] = custom_fields
    return request("POST", "/stories", data=payload)


def cmd_create_story_task(args: argparse.Namespace) -> dict:
    return request("POST", f"/stories/{args.story_id}/tasks", data={"description": args.description})


def cmd_delete_story_task(args: argparse.Namespace) -> dict:
    return request("DELETE", f"/stories/{args.story_id}/tasks/{args.task_id}")


def cmd_update_story(args: argparse.Namespace) -> dict:
    payload = {}
    mutable_fields = {
        "name": args.name,
        "description": args.description,
        "workflow_state_id": args.workflow_state_id,
        "project_id": args.project_id,
        "epic_id": args.epic_id,
        "group_id": args.group_id,
        "estimate": args.estimate,
        "story_type": args.story_type,
    }
    for key, value in mutable_fields.items():
        if value is not None:
            payload[key] = value
    if args.owner_ids is not None:
        payload["owner_ids"] = args.owner_ids
    labels = parse_json_arg(args.labels, "labels")
    labels_add = parse_json_arg(args.labels_add, "labels_add")
    labels_remove = parse_json_arg(args.labels_remove, "labels_remove")
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    custom_fields_add = parse_json_arg(args.custom_fields_add, "custom_fields_add")
    custom_fields_remove = parse_json_arg(args.custom_fields_remove, "custom_fields_remove")
    if labels is not None:
        payload["labels"] = labels
    if labels_add is not None:
        payload["labels_add"] = labels_add
    if labels_remove is not None:
        payload["labels_remove"] = labels_remove
    if custom_fields is not None:
        payload["custom_fields"] = custom_fields
    if custom_fields_add is not None:
        payload["custom_fields_add"] = custom_fields_add
    if custom_fields_remove is not None:
        payload["custom_fields_remove"] = custom_fields_remove

    if not payload:
        raise RuntimeError("No update fields provided")

    return request("PUT", f"/stories/{args.story_id}", data=payload)


def cmd_set_story_custom_fields(args: argparse.Namespace) -> dict:
    payload = {}
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    custom_fields_add = parse_json_arg(args.custom_fields_add, "custom_fields_add")
    custom_fields_remove = parse_json_arg(args.custom_fields_remove, "custom_fields_remove")
    if custom_fields is not None:
        payload["custom_fields"] = custom_fields
    if custom_fields_add is not None:
        payload["custom_fields_add"] = custom_fields_add
    if custom_fields_remove is not None:
        payload["custom_fields_remove"] = custom_fields_remove
    if not payload:
        raise RuntimeError("No custom field updates provided")
    return request("PUT", f"/stories/{args.story_id}", data=payload)


def cmd_update_story_labels(args: argparse.Namespace) -> dict:
    payload = {}
    labels = parse_json_arg(args.labels, "labels")
    labels_add = parse_json_arg(args.labels_add, "labels_add")
    labels_remove = parse_json_arg(args.labels_remove, "labels_remove")
    if labels is not None:
        payload["labels"] = labels
    if labels_add is not None:
        payload["labels_add"] = labels_add
    if labels_remove is not None:
        payload["labels_remove"] = labels_remove
    if not payload:
        raise RuntimeError("No label updates provided")
    return request("PUT", f"/stories/{args.story_id}", data=payload)


def cmd_update_epic_labels(args: argparse.Namespace) -> dict:
    payload = {}
    labels = parse_json_arg(args.labels, "labels")
    if labels is not None:
        payload["labels"] = labels
    if not payload:
        raise RuntimeError("No epic label updates provided")
    return request("PUT", f"/epics/{args.epic_id}", data=payload)


def cmd_comment_story(args: argparse.Namespace) -> dict:
    return request("POST", f"/stories/{args.story_id}/comments", data={"text": args.text})


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Shortcut task tracker CLI")
    sub = p.add_subparsers(dest="command", required=True)

    me = sub.add_parser("me", help="Get current authenticated member")
    me.set_defaults(func=cmd_me)

    search = sub.add_parser("search-stories", help="Search stories")
    search.add_argument("--query", required=True, help="Search query string")
    search.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    search.set_defaults(func=cmd_search_stories)

    list_stories = sub.add_parser("list-stories", help="List stories")
    list_stories.add_argument("--limit", type=int, default=25, help="Max results (default: 25)")
    list_stories.add_argument("--project-id", type=int)
    list_stories.add_argument("--workflow-state-id", type=int)
    list_stories.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    list_stories.set_defaults(func=cmd_list_stories)

    get_story = sub.add_parser("get-story", help="Fetch one story")
    get_story.add_argument("--story-id", type=int, required=True)
    get_story.set_defaults(func=cmd_get_story)

    list_projects = sub.add_parser("list-projects", help="List all projects")
    list_projects.set_defaults(func=cmd_list_projects)

    list_groups = sub.add_parser("list-groups", help="List teams/groups")
    list_groups.set_defaults(func=cmd_list_groups)

    create_group = sub.add_parser("create-group", help="Create a team/group")
    create_group.add_argument("--name", required=True)
    create_group.add_argument("--mention-name", required=True)
    create_group.add_argument("--description")
    create_group.add_argument("--color")
    create_group.add_argument("--color-key")
    create_group.add_argument("--member-ids", nargs="*")
    create_group.add_argument("--workflow-ids", type=int, nargs="*")
    create_group.set_defaults(func=cmd_create_group)

    ensure_group = sub.add_parser("ensure-group", help="Get or create a team/group")
    ensure_group.add_argument("--name", required=True)
    ensure_group.add_argument("--mention-name", required=True)
    ensure_group.add_argument("--description")
    ensure_group.add_argument("--color")
    ensure_group.add_argument("--color-key")
    ensure_group.add_argument("--member-ids", nargs="*")
    ensure_group.add_argument("--workflow-ids", type=int, nargs="*")
    ensure_group.set_defaults(func=cmd_ensure_group)

    create_project = sub.add_parser("create-project", help="Create a project")
    create_project.add_argument("--name", required=True)
    create_project.add_argument("--description")
    create_project.set_defaults(func=cmd_create_project)

    list_workflows = sub.add_parser("list-workflows", help="List workflows and states")
    list_workflows.set_defaults(func=cmd_list_workflows)

    list_epics = sub.add_parser("list-epics", help="List epics")
    list_epics.set_defaults(func=cmd_list_epics)

    create_epic = sub.add_parser("create-epic", help="Create an epic")
    create_epic.add_argument("--name", required=True)
    create_epic.add_argument("--description")
    create_epic.add_argument("--project-ids", type=int, nargs="*")
    create_epic.add_argument("--group-id")
    create_epic.add_argument("--owner-ids", nargs="*")
    create_epic.add_argument("--label-ids", type=int, nargs="*")
    create_epic.set_defaults(func=cmd_create_epic)

    update_epic = sub.add_parser("update-epic", help="Update an epic")
    update_epic.add_argument("--epic-id", type=int, required=True)
    update_epic.add_argument("--name")
    update_epic.add_argument("--description")
    update_epic.add_argument("--archived", action="store_true", help="Archive the epic")
    update_epic.add_argument("--project-ids", type=int, nargs="*")
    update_epic.add_argument("--group-id")
    update_epic.add_argument("--owner-ids", nargs="*")
    update_epic.add_argument("--labels", help="JSON array of label objects")
    update_epic.set_defaults(func=cmd_update_epic)

    update_epic_labels = sub.add_parser("update-epic-labels", help="Update epic labels")
    update_epic_labels.add_argument("--epic-id", type=int, required=True)
    update_epic_labels.add_argument("--labels", help="JSON array of label objects")
    update_epic_labels.set_defaults(func=cmd_update_epic_labels)

    list_members = sub.add_parser("list-members", help="List workspace members")
    list_members.set_defaults(func=cmd_list_members)

    list_labels = sub.add_parser("list-labels", help="List labels")
    list_labels.set_defaults(func=cmd_list_labels)

    list_custom_fields = sub.add_parser("list-custom-fields", help="List custom fields")
    list_custom_fields.set_defaults(func=cmd_list_custom_fields)

    get_custom_field = sub.add_parser("get-custom-field", help="Get one custom field")
    get_custom_field.add_argument("--custom-field-id", required=True)
    get_custom_field.set_defaults(func=cmd_get_custom_field)

    create_label = sub.add_parser("create-label", help="Create a label")
    create_label.add_argument("--name", required=True)
    create_label.add_argument("--color")
    create_label.add_argument("--description")
    create_label.set_defaults(func=cmd_create_label)

    create = sub.add_parser("create-story", help="Create a story")
    create.add_argument("--name", required=True)
    create.add_argument("--project-id", type=int)
    create.add_argument("--epic-id", type=int)
    create.add_argument("--group-id")
    create.add_argument("--parent-story-id", type=int)
    create.add_argument("--source-task-id", type=int)
    create.add_argument("--description")
    create.add_argument("--workflow-state-id", type=int)
    create.add_argument("--estimate", type=int)
    create.add_argument("--story-type", choices=["feature", "bug", "chore"])
    create.add_argument("--owner-ids", type=int, nargs="*")
    create.add_argument("--labels", help="JSON array of label objects, e.g. [{\"name\":\"High\"}]")
    create.add_argument(
        "--custom-fields",
        help="JSON array of custom field values, e.g. [{\"field_id\":\"...\",\"value_id\":\"...\"}]",
    )
    create.set_defaults(func=cmd_create_story)

    update = sub.add_parser("update-story", help="Update an existing story")
    update.add_argument("--story-id", type=int, required=True)
    update.add_argument("--name")
    update.add_argument("--description")
    update.add_argument("--workflow-state-id", type=int)
    update.add_argument("--project-id", type=int)
    update.add_argument("--epic-id", type=int)
    update.add_argument("--group-id")
    update.add_argument("--estimate", type=int)
    update.add_argument("--story-type", choices=["feature", "bug", "chore"])
    update.add_argument("--owner-ids", type=int, nargs="*")
    update.add_argument("--labels", help="JSON array of label objects")
    update.add_argument("--labels-add", help="JSON array of label objects to add")
    update.add_argument("--labels-remove", help="JSON array of label objects to remove")
    update.add_argument("--custom-fields", help="JSON array of custom field values")
    update.add_argument("--custom-fields-add", help="JSON array of custom field values to add")
    update.add_argument("--custom-fields-remove", help="JSON array of custom field removals")
    update.set_defaults(func=cmd_update_story)

    set_story_custom_fields = sub.add_parser("set-story-custom-fields", help="Update story custom fields")
    set_story_custom_fields.add_argument("--story-id", type=int, required=True)
    set_story_custom_fields.add_argument("--custom-fields", help="JSON array of custom field values")
    set_story_custom_fields.add_argument("--custom-fields-add", help="JSON array of custom field values to add")
    set_story_custom_fields.add_argument(
        "--custom-fields-remove",
        help="JSON array of custom field removals, e.g. [{\"field_id\":\"...\"}]",
    )
    set_story_custom_fields.set_defaults(func=cmd_set_story_custom_fields)

    update_story_labels = sub.add_parser("update-story-labels", help="Update story labels")
    update_story_labels.add_argument("--story-id", type=int, required=True)
    update_story_labels.add_argument("--labels", help="JSON array of label objects")
    update_story_labels.add_argument("--labels-add", help="JSON array of label objects to add")
    update_story_labels.add_argument("--labels-remove", help="JSON array of label objects to remove")
    update_story_labels.set_defaults(func=cmd_update_story_labels)

    create_task = sub.add_parser("create-story-task", help="Create a task on a story")
    create_task.add_argument("--story-id", type=int, required=True)
    create_task.add_argument("--description", required=True)
    create_task.set_defaults(func=cmd_create_story_task)

    delete_task = sub.add_parser("delete-story-task", help="Delete a task from a story")
    delete_task.add_argument("--story-id", type=int, required=True)
    delete_task.add_argument("--task-id", type=int, required=True)
    delete_task.set_defaults(func=cmd_delete_story_task)

    comment = sub.add_parser("comment-story", help="Add comment to a story")
    comment.add_argument("--story-id", type=int, required=True)
    comment.add_argument("--text", required=True)
    comment.set_defaults(func=cmd_comment_story)

    return p


def main() -> int:
    load_dotenv()
    p = parser()
    args = p.parse_args()

    try:
        result = args.func(args)
    except RuntimeError as err:
        print(str(err), file=sys.stderr)
        return 1

    if args.command == "list-stories" and not args.json:
        print(format_story_table(result))
        return 0

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
