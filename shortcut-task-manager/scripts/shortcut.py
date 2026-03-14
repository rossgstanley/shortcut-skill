#!/usr/bin/env python3
"""Minimal Shortcut API CLI for day-to-day story operations."""

import argparse
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid
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


def request_multipart(
    path: str,
    fields: Optional[dict] = None,
    files: Optional[list[dict]] = None,
) -> dict:
    token = os.environ.get("SHORTCUT_API_TOKEN")
    if not token:
        raise RuntimeError("Missing SHORTCUT_API_TOKEN environment variable")

    boundary = f"----ShortcutSkill{uuid.uuid4().hex}"
    body = bytearray()

    def add_bytes(value: bytes) -> None:
        body.extend(value)

    for key, value in (fields or {}).items():
        add_bytes(f"--{boundary}\r\n".encode("utf-8"))
        add_bytes(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode("utf-8"))
        add_bytes(str(value).encode("utf-8"))
        add_bytes(b"\r\n")

    for item in files or []:
        field_name = item["field_name"]
        file_path = item["path"]
        filename = item.get("filename") or os.path.basename(file_path)
        content_type = item.get("content_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        with open(file_path, "rb") as handle:
            file_bytes = handle.read()
        add_bytes(f"--{boundary}\r\n".encode("utf-8"))
        add_bytes(
            (
                f'Content-Disposition: form-data; name="{field_name}"; '
                f'filename="{filename}"\r\n'
            ).encode("utf-8")
        )
        add_bytes(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
        add_bytes(file_bytes)
        add_bytes(b"\r\n")

    add_bytes(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        url=build_url(path),
        data=bytes(body),
        headers={
            "Shortcut-Token": token,
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
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


def search_epics(query: str, limit: int) -> dict:
    return request("GET", "/search/epics", query={"query": query, "page_size": str(limit)})


def parse_json_arg(raw: Optional[str], field_name: str):
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"Invalid JSON for {field_name}: {err.msg}") from err


def normalize_name(value: str) -> str:
    return value.strip().lower()


def get_groups() -> list:
    return cmd_list_groups(argparse.Namespace())


def get_workflows() -> list:
    return cmd_list_workflows(argparse.Namespace())


def get_epics() -> list:
    return cmd_list_epics(argparse.Namespace())


def get_members() -> list:
    return cmd_list_members(argparse.Namespace())


def get_custom_fields() -> list:
    return cmd_list_custom_fields(argparse.Namespace())


def resolve_group_id(name: str) -> str:
    groups = get_groups()
    match = next((group for group in groups if normalize_name(group.get("name", "")) == normalize_name(name)), None)
    if match is None:
        raise RuntimeError(f"Unknown group/team: {name}")
    return match["id"]


def resolve_workflow_state_id(name: str) -> int:
    workflows = get_workflows()
    for workflow in workflows:
        for state in workflow.get("states", []):
            if normalize_name(state.get("name", "")) == normalize_name(name):
                return state["id"]
    raise RuntimeError(f"Unknown workflow state: {name}")


def resolve_epic_id(name: str) -> int:
    epics = [epic for epic in get_epics() if not epic.get("archived")]
    matches = [epic for epic in epics if normalize_name(epic.get("name", "")) == normalize_name(name)]
    if not matches:
        raise RuntimeError(f"Unknown epic: {name}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple active epics match: {name}")
    return matches[0]["id"]


def resolve_member_ids(names: list[str]) -> list[str]:
    members = get_members()
    resolved = []
    for name in names:
        match = next(
            (
                member
                for member in members
                if normalize_name(member.get("profile", {}).get("name", "")) == normalize_name(name)
                or normalize_name(member.get("profile", {}).get("mention_name", "")) == normalize_name(name)
                or normalize_name(member.get("mention_name", "")) == normalize_name(name)
                or normalize_name(member.get("name", "")) == normalize_name(name)
            ),
            None,
        )
        if match is None:
            raise RuntimeError(f"Unknown member: {name}")
        resolved.append(match["id"])
    return resolved


def resolve_custom_field_value(field_name: str, value_name: str) -> dict:
    field = next(
        (item for item in get_custom_fields() if normalize_name(item.get("name", "")) == normalize_name(field_name)),
        None,
    )
    if field is None:
        raise RuntimeError(f"Unknown custom field: {field_name}")
    value = next(
        (item for item in field.get("values", []) if normalize_name(item.get("value", "")) == normalize_name(value_name)),
        None,
    )
    if value is None:
        raise RuntimeError(f"Unknown value '{value_name}' for custom field '{field_name}'")
    return {"field_id": field["id"], "value_id": value["id"]}


def resolve_story_payload_args(args: argparse.Namespace, for_update: bool = False) -> dict:
    payload = {}
    if getattr(args, "workflow_state_name", None):
        payload["workflow_state_id"] = resolve_workflow_state_id(args.workflow_state_name)
    elif getattr(args, "workflow_state_id", None) is not None:
        payload["workflow_state_id"] = args.workflow_state_id

    if getattr(args, "group_name", None):
        payload["group_id"] = resolve_group_id(args.group_name)
    elif getattr(args, "group_id", None) is not None:
        payload["group_id"] = args.group_id

    if getattr(args, "epic_name", None):
        payload["epic_id"] = resolve_epic_id(args.epic_name)
    elif getattr(args, "epic_id", None) is not None:
        payload["epic_id"] = args.epic_id

    if getattr(args, "owner_self", False):
        payload["owner_ids"] = [cmd_me(argparse.Namespace())["id"]]
    elif getattr(args, "owner_names", None):
        payload["owner_ids"] = resolve_member_ids(args.owner_names)
    elif getattr(args, "owner_ids", None) is not None:
        payload["owner_ids"] = args.owner_ids

    if getattr(args, "label_names", None):
        payload["labels"] = [{"name": name} for name in args.label_names]
    return payload


def resolve_story_custom_fields_from_names(args: argparse.Namespace):
    if getattr(args, "field_name", None) and getattr(args, "value_name", None):
        return [resolve_custom_field_value(args.field_name, args.value_name)]
    return None


def validate_custom_field_payload_items(items, field_name: str) -> None:
    if items is None:
        return
    if not isinstance(items, list):
        raise RuntimeError(f"{field_name} must be a JSON array")

    custom_fields = {field.get("id"): field for field in get_custom_fields()}
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise RuntimeError(f"{field_name}[{index}] must be an object")
        field_id = item.get("field_id")
        if not field_id:
            continue
        custom_field = custom_fields.get(field_id)
        if custom_field is None:
            continue
        is_enum_field = bool(custom_field.get("values"))
        if is_enum_field and "value" in item and "value_id" not in item:
            custom_field_name = custom_field.get("name", field_id)
            raise RuntimeError(
                f"{field_name}[{index}] for enum custom field '{custom_field_name}' uses 'value'. "
                "Shortcut expects 'value_id'. Use --field-name/--value-name or send value_id explicitly."
            )


def enrich_story_records(stories: list[dict]) -> list[dict]:
    groups = {group["id"]: group.get("name", "") for group in get_groups()}
    for story in stories:
        story["team_name"] = groups.get(story.get("group_id"), "")
    return stories


def enrich_epic_records(epics: list[dict]) -> list[dict]:
    groups = {group["id"]: group.get("name", "") for group in get_groups()}
    for epic in epics:
        epic["team_name"] = groups.get(epic.get("group_id"), "")
    return epics


def format_story_table(payload: dict) -> str:
    stories = payload.get("data", [])
    if not stories:
        return "No stories found."

    groups = {group["id"]: group.get("name", "") for group in get_groups()}
    members = {member["id"]: member.get("profile", {}).get("name", member.get("name", "")) for member in get_members()}

    columns = [
        ("ID", lambda story: str(story.get("id", ""))),
        ("Name", lambda story: story.get("name", "")),
        ("Type", lambda story: story.get("story_type", "")),
        ("State", lambda story: story.get("workflow_state_name", str(story.get("workflow_state_id", "")))),
        ("Team", lambda story: groups.get(story.get("group_id"), "")),
        (
            "Owner",
            lambda story: ", ".join(members.get(owner_id, owner_id) for owner_id in story.get("owner_ids", [])[:2]),
        ),
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


def format_epic_table(payload) -> str:
    epics = payload.get("data", payload if isinstance(payload, list) else [])
    if not epics:
        return "No epics found."

    groups = {group["id"]: group.get("name", "") for group in get_groups()}
    members = {member["id"]: member.get("profile", {}).get("name", member.get("name", "")) for member in get_members()}

    columns = [
        ("ID", lambda epic: str(epic.get("id", ""))),
        ("Name", lambda epic: epic.get("name", "")),
        ("State", lambda epic: epic.get("state", "")),
        ("Team", lambda epic: groups.get(epic.get("group_id"), "")),
        (
            "Owner",
            lambda epic: ", ".join(members.get(owner_id, owner_id) for owner_id in epic.get("owner_ids", [])[:2]),
        ),
        ("Stories", lambda epic: str(epic.get("stats", {}).get("num_stories_total", ""))),
        ("Points", lambda epic: str(epic.get("stats", {}).get("num_points", ""))),
        ("URL", lambda epic: epic.get("app_url", "")),
    ]

    widths = []
    for header, getter in columns:
        max_width = len(header)
        for epic in epics:
            max_width = max(max_width, len(getter(epic)))
        widths.append(max_width)

    lines = []
    header_row = "  ".join(header.ljust(widths[index]) for index, (header, _) in enumerate(columns))
    divider = "  ".join("-" * widths[index] for index in range(len(columns)))
    lines.append(header_row)
    lines.append(divider)

    for epic in epics:
        row = "  ".join(
            getter(epic).ljust(widths[index]) for index, (_, getter) in enumerate(columns)
        )
        lines.append(row)

    return "\n".join(lines)


def format_refinement_table(payload: dict) -> str:
    stories = payload.get("data", [])
    if not stories:
        return "No refinement candidates found."

    columns = [
        ("ID", lambda story: str(story.get("id", ""))),
        ("Name", lambda story: story.get("name", "")),
        ("Team", lambda story: story.get("team_name", "")),
        ("Score", lambda story: str(story.get("refinement_score", ""))),
        ("Why", lambda story: story.get("refinement_explanation", "")),
        ("AgeDays", lambda story: str(story.get("age_days", ""))),
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


def format_next_story_table(payload: dict) -> str:
    stories = payload.get("data", [])
    if not stories:
        return "No next-story candidates found."

    columns = [
        ("ID", lambda story: str(story.get("id", ""))),
        ("Name", lambda story: story.get("name", "")),
        ("Team", lambda story: story.get("team_name", "")),
        ("Score", lambda story: str(story.get("next_score", ""))),
        ("Why", lambda story: story.get("next_explanation", "")),
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


def format_file_table(payload: dict) -> str:
    files = payload.get("data", payload if isinstance(payload, list) else [])
    if not files:
        return "No files found."

    columns = [
        ("PublicID", lambda item: str(item.get("id", item.get("public_id", "")))),
        ("Name", lambda item: item.get("name", item.get("filename", ""))),
        ("StoryID", lambda item: str(item.get("story_id", ""))),
        ("Size", lambda item: str(item.get("size", ""))),
        ("URL", lambda item: item.get("url", "")),
    ]

    widths = []
    for header, getter in columns:
        max_width = len(header)
        for item in files:
            max_width = max(max_width, len(getter(item)))
        widths.append(max_width)

    lines = []
    lines.append("  ".join(header.ljust(widths[index]) for index, (header, _) in enumerate(columns)))
    lines.append("  ".join("-" * widths[index] for index in range(len(columns))))
    for item in files:
        lines.append("  ".join(getter(item).ljust(widths[index]) for index, (_, getter) in enumerate(columns)))
    return "\n".join(lines)


def format_linked_file_table(payload: dict) -> str:
    files = payload.get("data", payload if isinstance(payload, list) else [])
    if not files:
        return "No linked files found."

    columns = [
        ("ID", lambda item: str(item.get("id", ""))),
        ("Name", lambda item: item.get("name", "")),
        ("StoryID", lambda item: str(item.get("story_id", ""))),
        ("Type", lambda item: item.get("type", "")),
        ("URL", lambda item: item.get("url", "")),
    ]

    widths = []
    for header, getter in columns:
        max_width = len(header)
        for item in files:
            max_width = max(max_width, len(getter(item)))
        widths.append(max_width)

    lines = []
    lines.append("  ".join(header.ljust(widths[index]) for index, (header, _) in enumerate(columns)))
    lines.append("  ".join("-" * widths[index] for index in range(len(columns))))
    for item in files:
        lines.append("  ".join(getter(item).ljust(widths[index]) for index, (_, getter) in enumerate(columns)))
    return "\n".join(lines)


def cmd_me(_: argparse.Namespace) -> dict:
    return request("GET", "/member")


def cmd_search_stories(args: argparse.Namespace) -> dict:
    result = search_stories(args.query, args.limit)
    return {
        **result,
        "data": enrich_story_records(result.get("data", [])),
    }


def cmd_search_epics(args: argparse.Namespace) -> dict:
    result = search_epics(args.query, args.limit)
    return {
        **result,
        "data": enrich_epic_records(result.get("data", [])),
    }


def cmd_list_stories(args: argparse.Namespace) -> dict:
    if getattr(args, "project_id", None) is not None:
        raise RuntimeError("Project filtering is not supported by list-stories yet")

    workflows = cmd_list_workflows(argparse.Namespace())
    state_names = {}
    states = []
    for workflow in workflows:
        for state in workflow.get("states", []):
            state_names[state["id"]] = state["name"]
            if getattr(args, "workflow_state_id", None) is not None and state.get("id") != args.workflow_state_id:
                continue
            if state.get("num_stories", 0) > 0:
                states.append(state)

    collect_limit = args.limit
    if getattr(args, "epic_id", None) is not None or getattr(args, "sort", None) is not None:
        collect_limit = 250

    stories = []
    seen_story_ids = set()
    for state in states:
        result = search_stories('state:"{0}"'.format(state["name"]), collect_limit)
        for story in result.get("data", []):
            story_id = story.get("id")
            if story_id in seen_story_ids:
                continue
            seen_story_ids.add(story_id)
            story["workflow_state_name"] = state_names.get(story.get("workflow_state_id"), "")
            stories.append(story)
            if len(stories) >= collect_limit:
                return {"data": enrich_story_records(stories), "next": None, "total": len(stories)}

    if getattr(args, "epic_id", None) is not None:
        stories = [story for story in stories if story.get("epic_id") == args.epic_id]
    if getattr(args, "active", False):
        stories = [story for story in stories if not story.get("archived", False)]
    if getattr(args, "sort", None) == "name":
        stories.sort(key=lambda story: story.get("name", "").lower())
    elif getattr(args, "sort", None) == "state":
        stories.sort(key=lambda story: story.get("workflow_state_name", "").lower())
    elif getattr(args, "sort", None) == "estimate":
        stories.sort(key=lambda story: -1 if story.get("estimate") is None else story.get("estimate"))
    stories = stories[: args.limit]
    return {"data": enrich_story_records(stories), "next": None, "total": len(stories)}


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


def cmd_list_epics(args: argparse.Namespace) -> dict:
    epics = request("GET", "/epics")
    if getattr(args, "active", False):
        epics = [epic for epic in epics if not epic.get("archived")]
    if getattr(args, "sort", None) == "name":
        epics.sort(key=lambda epic: epic.get("name", "").lower())
    elif getattr(args, "sort", None) == "stories":
        epics.sort(key=lambda epic: epic.get("stats", {}).get("num_stories_total", 0), reverse=True)
    elif getattr(args, "sort", None) == "points":
        epics.sort(key=lambda epic: epic.get("stats", {}).get("num_points", 0), reverse=True)
    return epics


def cmd_create_epic(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    if args.description is not None:
        payload["description"] = args.description
    if args.project_ids:
        payload["project_ids"] = args.project_ids
    if args.group_id is not None:
        payload["group_id"] = args.group_id
    if getattr(args, "owner_self", False):
        payload["owner_ids"] = [cmd_me(argparse.Namespace())["id"]]
    elif args.owner_ids:
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
    if getattr(args, "owner_self", False):
        payload["owner_ids"] = [cmd_me(argparse.Namespace())["id"]]
    elif args.owner_ids is not None:
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


def cmd_list_files(args: argparse.Namespace) -> dict:
    query = {}
    if getattr(args, "story_id", None) is not None:
        query["story_id"] = str(args.story_id)
    result = request("GET", "/files", query=query or None)
    files = result if isinstance(result, list) else result.get("data", [])
    return {"data": files}


def cmd_get_file(args: argparse.Namespace) -> dict:
    return request("GET", f"/files/{args.file_public_id}")


def cmd_upload_file(args: argparse.Namespace) -> dict:
    if not os.path.exists(args.path):
        raise RuntimeError(f"File not found: {args.path}")
    fields = {}
    if args.story_id is not None:
        fields["story_id"] = args.story_id
    return request_multipart(
        "/files",
        fields=fields,
        files=[
            {
                "field_name": "file",
                "path": args.path,
                "filename": args.name,
            }
        ],
    )


def cmd_list_linked_files(args: argparse.Namespace) -> dict:
    query = {}
    if getattr(args, "story_id", None) is not None:
        query["story_id"] = str(args.story_id)
    result = request("GET", "/linked-files", query=query or None)
    files = result if isinstance(result, list) else result.get("data", [])
    return {"data": files}


def cmd_get_linked_file(args: argparse.Namespace) -> dict:
    return request("GET", f"/linked-files/{args.linked_file_id}")


def cmd_create_linked_file(args: argparse.Namespace) -> dict:
    payload = {"name": args.name, "type": args.type, "url": args.url}
    if args.story_id is not None:
        payload["story_id"] = args.story_id
    return request("POST", "/linked-files", data=payload)


def cmd_create_story(args: argparse.Namespace) -> dict:
    payload = {"name": args.name}
    optional_fields = {
        "description": args.description,
        "estimate": args.estimate,
        "story_type": args.story_type,
        "project_id": args.project_id,
        "parent_story_id": args.parent_story_id,
        "source_task_id": args.source_task_id,
    }
    for key, value in optional_fields.items():
        if value is not None:
            payload[key] = value
    payload.update(resolve_story_payload_args(args))
    labels = parse_json_arg(args.labels, "labels")
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    validate_custom_field_payload_items(custom_fields, "custom_fields")
    named_custom_fields = resolve_story_custom_fields_from_names(args)
    if labels is not None:
        payload["labels"] = labels
    elif "labels" in payload:
        pass
    if custom_fields is not None:
        payload["custom_fields"] = custom_fields
    elif named_custom_fields is not None:
        payload["custom_fields"] = named_custom_fields
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
        "project_id": args.project_id,
        "estimate": args.estimate,
        "story_type": args.story_type,
    }
    for key, value in mutable_fields.items():
        if value is not None:
            payload[key] = value
    payload.update(resolve_story_payload_args(args, for_update=True))
    labels = parse_json_arg(args.labels, "labels")
    labels_add = parse_json_arg(args.labels_add, "labels_add")
    labels_remove = parse_json_arg(args.labels_remove, "labels_remove")
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    custom_fields_add = parse_json_arg(args.custom_fields_add, "custom_fields_add")
    custom_fields_remove = parse_json_arg(args.custom_fields_remove, "custom_fields_remove")
    validate_custom_field_payload_items(custom_fields, "custom_fields")
    validate_custom_field_payload_items(custom_fields_add, "custom_fields_add")
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
    named_custom_fields = resolve_story_custom_fields_from_names(args)
    if named_custom_fields is not None:
        payload["custom_fields"] = named_custom_fields

    if not payload:
        raise RuntimeError("No update fields provided")

    return request("PUT", f"/stories/{args.story_id}", data=payload)


def cmd_validate_story_update(args: argparse.Namespace) -> dict:
    payload_args = argparse.Namespace(
        workflow_state_id=args.workflow_state_id,
        workflow_state_name=args.workflow_state_name,
        group_id=args.group_id,
        group_name=args.group_name,
        epic_id=args.epic_id,
        epic_name=args.epic_name,
        owner_self=args.owner_self,
        owner_ids=args.owner_ids,
        owner_names=args.owner_names,
        label_names=args.label_names,
        field_name=args.field_name,
        value_name=args.value_name,
    )

    payload = {}
    mutable_fields = {
        "name": args.name,
        "description": args.description,
        "project_id": args.project_id,
        "estimate": args.estimate,
        "story_type": args.story_type,
    }
    for key, value in mutable_fields.items():
        if value is not None:
            payload[key] = value

    payload.update(resolve_story_payload_args(payload_args, for_update=True))
    labels = parse_json_arg(args.labels, "labels")
    labels_add = parse_json_arg(args.labels_add, "labels_add")
    labels_remove = parse_json_arg(args.labels_remove, "labels_remove")
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    custom_fields_add = parse_json_arg(args.custom_fields_add, "custom_fields_add")
    custom_fields_remove = parse_json_arg(args.custom_fields_remove, "custom_fields_remove")
    validate_custom_field_payload_items(custom_fields, "custom_fields")
    validate_custom_field_payload_items(custom_fields_add, "custom_fields_add")

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

    named_custom_fields = resolve_story_custom_fields_from_names(payload_args)
    if named_custom_fields is not None:
        payload["custom_fields"] = named_custom_fields

    if not payload:
        raise RuntimeError("No update fields provided")

    return {
        "dry_run": True,
        "action": "validate-story-update",
        "story_id": args.story_id,
        "payload": payload,
    }


def cmd_set_story_custom_field(args: argparse.Namespace) -> dict:
    custom_field_value = resolve_custom_field_value(args.field_name, args.value_name)
    payload = {"story_id": args.story_id, "custom_fields": [custom_field_value]}
    if args.dry_run:
        return {"dry_run": True, "action": "set-story-custom-field", "payload": payload}
    return request("PUT", f"/stories/{args.story_id}", data={"custom_fields": [custom_field_value]})


def cmd_bulk_update_stories(args: argparse.Namespace) -> dict:
    stories = search_stories(args.query, args.limit).get("data", [])
    if args.epic_name:
        epic_id = resolve_epic_id(args.epic_name)
        stories = [story for story in stories if story.get("epic_id") == epic_id]

    payload_args = argparse.Namespace(
        workflow_state_id=args.workflow_state_id,
        workflow_state_name=args.workflow_state_name,
        group_id=args.group_id,
        group_name=args.group_name,
        epic_id=args.epic_id,
        epic_name=args.epic_name_target,
        owner_self=args.owner_self,
        owner_ids=args.owner_ids,
        owner_names=args.owner_names,
        label_names=args.label_names,
        field_name=args.field_name,
        value_name=args.value_name,
    )
    resolved_payload = resolve_story_payload_args(payload_args, for_update=True)
    named_custom_fields = resolve_story_custom_fields_from_names(payload_args)
    if named_custom_fields is not None:
        resolved_payload["custom_fields"] = named_custom_fields
    if args.story_type is not None:
        resolved_payload["story_type"] = args.story_type
    if args.estimate is not None:
        resolved_payload["estimate"] = args.estimate
    if not resolved_payload:
        raise RuntimeError("No bulk update fields provided")

    preview = {
        "count": len(stories),
        "story_ids": [story["id"] for story in stories],
        "changes": resolved_payload,
    }
    if args.dry_run:
        return {"dry_run": True, "preview": preview}
    if len(stories) > 1 and not args.yes:
        raise RuntimeError("Bulk update would affect multiple stories. Rerun with --yes or --dry-run.")
    updated = []
    for story in stories:
        updated.append(request("PUT", f"/stories/{story['id']}", data=resolved_payload))
    return {"updated": updated, "preview": preview}


def priority_rank(story: dict) -> int:
    field_values = story.get("custom_fields", [])
    for field in field_values:
        if normalize_name(field.get("name", "")) == "priority":
            value = normalize_name(field.get("value", ""))
            ranks = {"highest": 5, "high": 4, "medium": 3, "low": 2, "lowest": 1}
            return ranks.get(value, 0)
    return 0


def age_days(story: dict) -> int:
    created_at = story.get("created_at", "")
    if not created_at or len(created_at) < 10:
        return 0
    try:
        from datetime import date

        created = date.fromisoformat(created_at[:10])
        return max((date.today() - created).days, 0)
    except ValueError:
        return 0


def cmd_next_stories(args: argparse.Namespace) -> dict:
    epic_done_map = {
        epic["id"]: epic.get("stats", {}).get("num_stories_done", 0)
        for epic in cmd_list_epics(argparse.Namespace(active=True, sort=None))
    }
    stories = cmd_list_stories(
        argparse.Namespace(
            limit=max(args.limit * 10, 50),
            project_id=None,
            workflow_state_id=None,
            epic_id=resolve_epic_id(args.epic_name) if args.epic_name else None,
            active=True,
            sort=None,
        )
    ).get("data", [])
    candidates = []
    for story in stories:
        state_name = normalize_name(story.get("workflow_state_name", ""))
        if state_name not in {"backlog", "to do"}:
            continue
        if args.group_name and story.get("group_id") != resolve_group_id(args.group_name):
            continue
        if args.exclude_subtasks and story.get("parent_story_id") is not None:
            continue
        story["age_days"] = age_days(story)
        story["epic_has_done_work"] = epic_done_map.get(story.get("epic_id"), 0) > 0
        candidates.append(story)

    def score(story: dict) -> int:
        total = 0
        total += priority_rank(story) * 100
        total += min(story.get("age_days", 0), 365)
        if story.get("epic_id") is not None:
            total += 20
        if story.get("description"):
            total += 10
        if story.get("epic_has_done_work"):
            total += 15
        return total

    for story in candidates:
        reasons = []
        if priority_rank(story):
            reasons.append(f"priority={priority_rank(story)}")
        if story.get("age_days", 0):
            reasons.append(f"age={story['age_days']}d")
        if story.get("epic_id") is not None:
            reasons.append("has epic")
        if story.get("description"):
            reasons.append("has description")
        if story.get("epic_has_done_work"):
            reasons.append("epic has done work")
        story["next_score"] = score(story)
        story["next_explanation"] = ", ".join(reasons)
        story.pop("workflow_state_name", None)
        story.pop("workflow_state_id", None)

    candidates.sort(key=lambda story: (-story["next_score"], story.get("name", "").lower()))
    return {"data": candidates[: args.limit], "total": len(candidates)}


def cmd_refinement_list(args: argparse.Namespace) -> dict:
    stories = cmd_list_stories(
        argparse.Namespace(
            limit=max(args.limit * 10, 100),
            project_id=None,
            workflow_state_id=None,
            epic_id=None,
            active=True,
            sort=None,
        )
    ).get("data", [])
    candidates = []
    for story in stories:
        issues = []
        if story.get("epic_id") is None:
            issues.append("no epic")
        if not story.get("description"):
            issues.append("no description")
        if priority_rank(story) == 0:
            issues.append("no priority")
        if not story.get("owner_ids"):
            issues.append("no owner")
        if issues:
            story["refinement_issues"] = issues
            story["age_days"] = age_days(story)
            story["refinement_score"] = len(issues) * 100 + min(story["age_days"], 365)
            story["refinement_explanation"] = ", ".join(issues)
            story.pop("workflow_state_name", None)
            story.pop("workflow_state_id", None)
            candidates.append(story)

    candidates.sort(
        key=lambda story: (
            -story.get("refinement_score", 0),
            story.get("name", "").lower(),
        )
    )
    return {"data": candidates[: args.limit], "total": len(candidates)}


def cmd_set_story_custom_fields(args: argparse.Namespace) -> dict:
    payload = {}
    custom_fields = parse_json_arg(args.custom_fields, "custom_fields")
    custom_fields_add = parse_json_arg(args.custom_fields_add, "custom_fields_add")
    custom_fields_remove = parse_json_arg(args.custom_fields_remove, "custom_fields_remove")
    validate_custom_field_payload_items(custom_fields, "custom_fields")
    validate_custom_field_payload_items(custom_fields_add, "custom_fields_add")
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
    search.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    search.set_defaults(func=cmd_search_stories)

    search_epics_parser = sub.add_parser("search-epics", help="Search epics")
    search_epics_parser.add_argument("--query", required=True, help="Search query string")
    search_epics_parser.add_argument("--limit", type=int, default=10, help="Max results (default: 10)")
    search_epics_parser.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    search_epics_parser.set_defaults(func=cmd_search_epics)

    list_stories = sub.add_parser("list-stories", help="List stories")
    list_stories.add_argument("--limit", type=int, default=25, help="Max results (default: 25)")
    list_stories.add_argument("--project-id", type=int)
    list_stories.add_argument("--workflow-state-id", type=int)
    list_stories.add_argument("--epic-id", type=int)
    list_stories.add_argument("--active", action="store_true", help="Only include active stories")
    list_stories.add_argument("--sort", choices=["name", "state", "estimate"])
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
    list_epics.add_argument("--active", action="store_true", help="Only include active epics")
    list_epics.add_argument("--sort", choices=["name", "stories", "points"])
    list_epics.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    list_epics.set_defaults(func=cmd_list_epics)

    create_epic = sub.add_parser("create-epic", help="Create an epic")
    create_epic.add_argument("--name", required=True)
    create_epic.add_argument("--description")
    create_epic.add_argument("--project-ids", type=int, nargs="*")
    create_epic.add_argument("--group-id")
    create_epic.add_argument("--owner-self", action="store_true")
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
    update_epic.add_argument("--owner-self", action="store_true")
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

    list_files = sub.add_parser("list-files", help="List uploaded files")
    list_files.add_argument("--story-id", type=int)
    list_files.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    list_files.set_defaults(func=cmd_list_files)

    get_file = sub.add_parser("get-file", help="Get one uploaded file")
    get_file.add_argument("--file-public-id", required=True)
    get_file.set_defaults(func=cmd_get_file)

    upload_file = sub.add_parser("upload-file", help="Upload a file or image")
    upload_file.add_argument("--path", required=True)
    upload_file.add_argument("--name")
    upload_file.add_argument("--story-id", type=int)
    upload_file.set_defaults(func=cmd_upload_file)

    list_linked_files = sub.add_parser("list-linked-files", help="List linked files")
    list_linked_files.add_argument("--story-id", type=int)
    list_linked_files.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    list_linked_files.set_defaults(func=cmd_list_linked_files)

    get_linked_file = sub.add_parser("get-linked-file", help="Get one linked file")
    get_linked_file.add_argument("--linked-file-id", required=True)
    get_linked_file.set_defaults(func=cmd_get_linked_file)

    create_linked_file = sub.add_parser("create-linked-file", help="Create a linked file")
    create_linked_file.add_argument("--name", required=True)
    create_linked_file.add_argument("--url", required=True)
    create_linked_file.add_argument("--type", default="url")
    create_linked_file.add_argument("--story-id", type=int)
    create_linked_file.set_defaults(func=cmd_create_linked_file)

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
    create.add_argument("--epic-name")
    create.add_argument("--group-id")
    create.add_argument("--group-name")
    create.add_argument("--parent-story-id", type=int)
    create.add_argument("--source-task-id", type=int)
    create.add_argument("--description")
    create.add_argument("--workflow-state-id", type=int)
    create.add_argument("--workflow-state-name")
    create.add_argument("--estimate", type=int)
    create.add_argument("--story-type", choices=["feature", "bug", "chore"])
    create.add_argument("--owner-self", action="store_true")
    create.add_argument("--owner-ids", nargs="*")
    create.add_argument("--owner-names", nargs="*")
    create.add_argument("--label-names", nargs="*")
    create.add_argument("--field-name")
    create.add_argument("--value-name")
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
    update.add_argument("--workflow-state-name")
    update.add_argument("--project-id", type=int)
    update.add_argument("--epic-id", type=int)
    update.add_argument("--epic-name")
    update.add_argument("--group-id")
    update.add_argument("--group-name")
    update.add_argument("--estimate", type=int)
    update.add_argument("--story-type", choices=["feature", "bug", "chore"])
    update.add_argument("--owner-self", action="store_true")
    update.add_argument("--owner-ids", nargs="*")
    update.add_argument("--owner-names", nargs="*")
    update.add_argument("--label-names", nargs="*")
    update.add_argument("--field-name")
    update.add_argument("--value-name")
    update.add_argument("--labels", help="JSON array of label objects")
    update.add_argument("--labels-add", help="JSON array of label objects to add")
    update.add_argument("--labels-remove", help="JSON array of label objects to remove")
    update.add_argument("--custom-fields", help="JSON array of custom field values")
    update.add_argument("--custom-fields-add", help="JSON array of custom field values to add")
    update.add_argument("--custom-fields-remove", help="JSON array of custom field removals")
    update.set_defaults(func=cmd_update_story)

    validate_story_update = sub.add_parser("validate-story-update", help="Validate and preview a story update payload")
    validate_story_update.add_argument("--story-id", type=int, required=True)
    validate_story_update.add_argument("--name")
    validate_story_update.add_argument("--description")
    validate_story_update.add_argument("--workflow-state-id", type=int)
    validate_story_update.add_argument("--workflow-state-name")
    validate_story_update.add_argument("--project-id", type=int)
    validate_story_update.add_argument("--epic-id", type=int)
    validate_story_update.add_argument("--epic-name")
    validate_story_update.add_argument("--group-id")
    validate_story_update.add_argument("--group-name")
    validate_story_update.add_argument("--estimate", type=int)
    validate_story_update.add_argument("--story-type", choices=["feature", "bug", "chore"])
    validate_story_update.add_argument("--owner-self", action="store_true")
    validate_story_update.add_argument("--owner-ids", nargs="*")
    validate_story_update.add_argument("--owner-names", nargs="*")
    validate_story_update.add_argument("--label-names", nargs="*")
    validate_story_update.add_argument("--field-name")
    validate_story_update.add_argument("--value-name")
    validate_story_update.add_argument("--labels", help="JSON array of label objects")
    validate_story_update.add_argument("--labels-add", help="JSON array of label objects to add")
    validate_story_update.add_argument("--labels-remove", help="JSON array of label objects to remove")
    validate_story_update.add_argument("--custom-fields", help="JSON array of custom field values")
    validate_story_update.add_argument("--custom-fields-add", help="JSON array of custom field values to add")
    validate_story_update.add_argument("--custom-fields-remove", help="JSON array of custom field removals")
    validate_story_update.set_defaults(func=cmd_validate_story_update)

    set_story_custom_fields = sub.add_parser("set-story-custom-fields", help="Update story custom fields")
    set_story_custom_fields.add_argument("--story-id", type=int, required=True)
    set_story_custom_fields.add_argument("--custom-fields", help="JSON array of custom field values")
    set_story_custom_fields.add_argument("--custom-fields-add", help="JSON array of custom field values to add")
    set_story_custom_fields.add_argument(
        "--custom-fields-remove",
        help="JSON array of custom field removals, e.g. [{\"field_id\":\"...\"}]",
    )
    set_story_custom_fields.set_defaults(func=cmd_set_story_custom_fields)

    set_story_custom_field = sub.add_parser("set-story-custom-field", help="Set one story custom field by name")
    set_story_custom_field.add_argument("--story-id", type=int, required=True)
    set_story_custom_field.add_argument("--field-name", required=True)
    set_story_custom_field.add_argument("--value-name", required=True)
    set_story_custom_field.add_argument("--dry-run", action="store_true")
    set_story_custom_field.set_defaults(func=cmd_set_story_custom_field)

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

    bulk_update_stories = sub.add_parser("bulk-update-stories", help="Bulk update stories found by search query")
    bulk_update_stories.add_argument("--query", required=True)
    bulk_update_stories.add_argument("--limit", type=int, default=100)
    bulk_update_stories.add_argument("--workflow-state-id", type=int)
    bulk_update_stories.add_argument("--workflow-state-name")
    bulk_update_stories.add_argument("--group-id")
    bulk_update_stories.add_argument("--group-name")
    bulk_update_stories.add_argument("--epic-name")
    bulk_update_stories.add_argument("--epic-id", type=int)
    bulk_update_stories.add_argument("--epic-name-target")
    bulk_update_stories.add_argument("--owner-self", action="store_true")
    bulk_update_stories.add_argument("--owner-ids", nargs="*")
    bulk_update_stories.add_argument("--owner-names", nargs="*")
    bulk_update_stories.add_argument("--label-names", nargs="*")
    bulk_update_stories.add_argument("--field-name")
    bulk_update_stories.add_argument("--value-name")
    bulk_update_stories.add_argument("--estimate", type=int)
    bulk_update_stories.add_argument("--story-type", choices=["feature", "bug", "chore"])
    bulk_update_stories.add_argument("--dry-run", action="store_true")
    bulk_update_stories.add_argument("--yes", action="store_true")
    bulk_update_stories.set_defaults(func=cmd_bulk_update_stories)

    next_stories = sub.add_parser("next-stories", help="Rank the next stories to work on")
    next_stories.add_argument("--limit", type=int, default=10)
    next_stories.add_argument("--group-name")
    next_stories.add_argument("--epic-name")
    next_stories.add_argument("--exclude-subtasks", action="store_true")
    next_stories.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    next_stories.set_defaults(func=cmd_next_stories)

    refinement_list = sub.add_parser("refinement-list", help="Rank stories that need refinement")
    refinement_list.add_argument("--limit", type=int, default=10)
    refinement_list.add_argument("--json", action="store_true", help="Print raw JSON instead of a table")
    refinement_list.set_defaults(func=cmd_refinement_list)

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

    if args.command in {"list-stories", "search-stories"} and not args.json:
        print(format_story_table(result))
        return 0

    if args.command == "next-stories" and not args.json:
        print(format_next_story_table(result))
        return 0

    if args.command == "refinement-list" and not args.json:
        print(format_refinement_table(result))
        return 0

    if args.command in {"list-epics", "search-epics"} and not args.json:
        print(format_epic_table(result))
        return 0

    if args.command == "list-files" and not args.json:
        print(format_file_table(result))
        return 0

    if args.command == "list-linked-files" and not args.json:
        print(format_linked_file_table(result))
        return 0

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
