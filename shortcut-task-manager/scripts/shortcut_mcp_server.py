#!/usr/bin/env python3
"""Minimal MCP server exposing Shortcut operations over stdio."""

import json
import sys
from typing import Any, Dict, List, Optional

import shortcut

SERVER_INFO = {
    "name": "shortcut-task-manager",
    "version": "0.1.0",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "shortcut_me",
        "description": "Get the current authenticated Shortcut member.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_search_stories",
        "description": "Search Shortcut stories by free-text query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "default": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_list_stories",
        "description": "List Shortcut stories, optionally filtered by workflow state.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "minimum": 1, "default": 25},
                "workflow_state_id": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_get_story",
        "description": "Fetch a single Shortcut story by ID.",
        "inputSchema": {
            "type": "object",
            "properties": {"story_id": {"type": "integer"}},
            "required": ["story_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_list_projects",
        "description": "List Shortcut projects.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_list_groups",
        "description": "List Shortcut teams/groups.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_create_group",
        "description": "Create a Shortcut team/group.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "mention_name": {"type": "string"},
                "description": {"type": "string"},
                "color": {"type": "string"},
                "color_key": {"type": "string"},
                "member_ids": {"type": "array", "items": {"type": "string"}},
                "workflow_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["name", "mention_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_ensure_group",
        "description": "Get or create a Shortcut team/group by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "mention_name": {"type": "string"},
                "description": {"type": "string"},
                "color": {"type": "string"},
                "color_key": {"type": "string"},
                "member_ids": {"type": "array", "items": {"type": "string"}},
                "workflow_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["name", "mention_name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_create_project",
        "description": "Create a Shortcut project.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_list_workflows",
        "description": "List Shortcut workflows and workflow states.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_list_epics",
        "description": "List Shortcut epics.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_list_members",
        "description": "List Shortcut members.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_list_labels",
        "description": "List Shortcut labels.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_list_custom_fields",
        "description": "List Shortcut custom fields.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "shortcut_get_custom_field",
        "description": "Get one Shortcut custom field.",
        "inputSchema": {
            "type": "object",
            "properties": {"custom_field_id": {"type": "string"}},
            "required": ["custom_field_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_create_label",
        "description": "Create a Shortcut label.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "color": {"type": "string"},
                "description": {"type": "string"},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_create_story",
        "description": "Create a Shortcut story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "project_id": {"type": "integer"},
                "epic_id": {"type": "integer"},
                "group_id": {"type": "string"},
                "parent_story_id": {"type": "integer"},
                "source_task_id": {"type": "integer"},
                "description": {"type": "string"},
                "workflow_state_id": {"type": "integer"},
                "estimate": {"type": "integer"},
                "story_type": {"type": "string", "enum": ["feature", "bug", "chore"]},
                "owner_ids": {"type": "array", "items": {"type": "integer"}},
                "labels": {"type": "array", "items": {"type": "object"}},
                "custom_fields": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_create_epic",
        "description": "Create a Shortcut epic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "project_ids": {"type": "array", "items": {"type": "integer"}},
                "group_id": {"type": "string"},
                "owner_ids": {"type": "array", "items": {"type": "string"}},
                "label_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_update_epic",
        "description": "Update a Shortcut epic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "project_ids": {"type": "array", "items": {"type": "integer"}},
                "group_id": {"type": "string"},
                "owner_ids": {"type": "array", "items": {"type": "string"}},
                "labels": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["epic_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_update_epic_labels",
        "description": "Update labels on a Shortcut epic.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "epic_id": {"type": "integer"},
                "labels": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["epic_id", "labels"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_update_story",
        "description": "Update a Shortcut story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "workflow_state_id": {"type": "integer"},
                "project_id": {"type": "integer"},
                "epic_id": {"type": "integer"},
                "group_id": {"type": "string"},
                "estimate": {"type": "integer"},
                "story_type": {"type": "string", "enum": ["feature", "bug", "chore"]},
                "owner_ids": {"type": "array", "items": {"type": "integer"}},
                "labels": {"type": "array", "items": {"type": "object"}},
                "labels_add": {"type": "array", "items": {"type": "object"}},
                "labels_remove": {"type": "array", "items": {"type": "object"}},
                "custom_fields": {"type": "array", "items": {"type": "object"}},
                "custom_fields_add": {"type": "array", "items": {"type": "object"}},
                "custom_fields_remove": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["story_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_set_story_custom_fields",
        "description": "Update custom fields on a Shortcut story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer"},
                "custom_fields": {"type": "array", "items": {"type": "object"}},
                "custom_fields_add": {"type": "array", "items": {"type": "object"}},
                "custom_fields_remove": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["story_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_update_story_labels",
        "description": "Update labels on a Shortcut story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer"},
                "labels": {"type": "array", "items": {"type": "object"}},
                "labels_add": {"type": "array", "items": {"type": "object"}},
                "labels_remove": {"type": "array", "items": {"type": "object"}},
            },
            "required": ["story_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "shortcut_comment_story",
        "description": "Add a comment to a Shortcut story.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "story_id": {"type": "integer"},
                "text": {"type": "string"},
            },
            "required": ["story_id", "text"],
            "additionalProperties": False,
        },
    },
]


def make_args(**kwargs: Any) -> object:
    return type("Args", (), kwargs)()


def call_tool(name: str, arguments: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    args = arguments or {}

    if name == "shortcut_me":
        return shortcut.cmd_me(make_args())
    if name == "shortcut_search_stories":
        return shortcut.cmd_search_stories(make_args(query=args["query"], limit=args.get("limit", 10)))
    if name == "shortcut_list_stories":
        return shortcut.cmd_list_stories(
            make_args(
                limit=args.get("limit", 25),
                project_id=None,
                workflow_state_id=args.get("workflow_state_id"),
            )
        )
    if name == "shortcut_get_story":
        return shortcut.cmd_get_story(make_args(story_id=args["story_id"]))
    if name == "shortcut_list_projects":
        return shortcut.cmd_list_projects(make_args())
    if name == "shortcut_list_groups":
        return shortcut.cmd_list_groups(make_args())
    if name == "shortcut_create_group":
        return shortcut.cmd_create_group(
            make_args(
                name=args["name"],
                mention_name=args["mention_name"],
                description=args.get("description"),
                color=args.get("color"),
                color_key=args.get("color_key"),
                member_ids=args.get("member_ids"),
                workflow_ids=args.get("workflow_ids"),
            )
        )
    if name == "shortcut_ensure_group":
        return shortcut.cmd_ensure_group(
            make_args(
                name=args["name"],
                mention_name=args["mention_name"],
                description=args.get("description"),
                color=args.get("color"),
                color_key=args.get("color_key"),
                member_ids=args.get("member_ids"),
                workflow_ids=args.get("workflow_ids"),
            )
        )
    if name == "shortcut_create_project":
        return shortcut.cmd_create_project(make_args(name=args["name"], description=args.get("description")))
    if name == "shortcut_list_workflows":
        return shortcut.cmd_list_workflows(make_args())
    if name == "shortcut_list_epics":
        return shortcut.cmd_list_epics(make_args())
    if name == "shortcut_list_members":
        return shortcut.cmd_list_members(make_args())
    if name == "shortcut_list_labels":
        return shortcut.cmd_list_labels(make_args())
    if name == "shortcut_list_custom_fields":
        return shortcut.cmd_list_custom_fields(make_args())
    if name == "shortcut_get_custom_field":
        return shortcut.cmd_get_custom_field(make_args(custom_field_id=args["custom_field_id"]))
    if name == "shortcut_create_label":
        return shortcut.cmd_create_label(
            make_args(
                name=args["name"],
                color=args.get("color"),
                description=args.get("description"),
            )
        )
    if name == "shortcut_create_story":
        return shortcut.cmd_create_story(
            make_args(
                name=args["name"],
                project_id=args.get("project_id"),
                epic_id=args.get("epic_id"),
                group_id=args.get("group_id"),
                parent_story_id=args.get("parent_story_id"),
                source_task_id=args.get("source_task_id"),
                description=args.get("description"),
                workflow_state_id=args.get("workflow_state_id"),
                estimate=args.get("estimate"),
                story_type=args.get("story_type"),
                owner_ids=args.get("owner_ids"),
                labels=json.dumps(args["labels"]) if "labels" in args else None,
                custom_fields=json.dumps(args["custom_fields"]) if "custom_fields" in args else None,
            )
        )
    if name == "shortcut_create_epic":
        return shortcut.cmd_create_epic(
            make_args(
                name=args["name"],
                description=args.get("description"),
                project_ids=args.get("project_ids"),
                group_id=args.get("group_id"),
                owner_ids=args.get("owner_ids"),
                label_ids=args.get("label_ids"),
            )
        )
    if name == "shortcut_update_epic_labels":
        return shortcut.cmd_update_epic_labels(
            make_args(
                epic_id=args["epic_id"],
                labels=json.dumps(args["labels"]),
            )
        )
    if name == "shortcut_update_epic":
        return shortcut.cmd_update_epic(
            make_args(
                epic_id=args["epic_id"],
                name=args.get("name"),
                description=args.get("description"),
                project_ids=args.get("project_ids"),
                group_id=args.get("group_id"),
                owner_ids=args.get("owner_ids"),
                labels=json.dumps(args["labels"]) if "labels" in args else None,
            )
        )
    if name == "shortcut_update_story":
        return shortcut.cmd_update_story(
            make_args(
                story_id=args["story_id"],
                name=args.get("name"),
                description=args.get("description"),
                workflow_state_id=args.get("workflow_state_id"),
                project_id=args.get("project_id"),
                epic_id=args.get("epic_id"),
                group_id=args.get("group_id"),
                estimate=args.get("estimate"),
                story_type=args.get("story_type"),
                owner_ids=args.get("owner_ids"),
                labels=json.dumps(args["labels"]) if "labels" in args else None,
                labels_add=json.dumps(args["labels_add"]) if "labels_add" in args else None,
                labels_remove=json.dumps(args["labels_remove"]) if "labels_remove" in args else None,
                custom_fields=json.dumps(args["custom_fields"]) if "custom_fields" in args else None,
                custom_fields_add=json.dumps(args["custom_fields_add"]) if "custom_fields_add" in args else None,
                custom_fields_remove=json.dumps(args["custom_fields_remove"]) if "custom_fields_remove" in args else None,
            )
        )
    if name == "shortcut_set_story_custom_fields":
        return shortcut.cmd_set_story_custom_fields(
            make_args(
                story_id=args["story_id"],
                custom_fields=json.dumps(args["custom_fields"]) if "custom_fields" in args else None,
                custom_fields_add=json.dumps(args["custom_fields_add"]) if "custom_fields_add" in args else None,
                custom_fields_remove=json.dumps(args["custom_fields_remove"]) if "custom_fields_remove" in args else None,
            )
        )
    if name == "shortcut_update_story_labels":
        return shortcut.cmd_update_story_labels(
            make_args(
                story_id=args["story_id"],
                labels=json.dumps(args["labels"]) if "labels" in args else None,
                labels_add=json.dumps(args["labels_add"]) if "labels_add" in args else None,
                labels_remove=json.dumps(args["labels_remove"]) if "labels_remove" in args else None,
            )
        )
    if name == "shortcut_comment_story":
        return shortcut.cmd_comment_story(make_args(story_id=args["story_id"], text=args["text"]))

    raise ValueError("Unknown tool: {0}".format(name))

def write_message(message: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message) + "\n")
    sys.stdout.flush()

def read_message() -> Optional[Dict[str, Any]]:
    line = sys.stdin.readline()
    if not line:
        return None
    return json.loads(line.strip())

def handle_request(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    method = message.get("method")
    request_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": params.get("protocolVersion", "2025-11-05"),
                "serverInfo": SERVER_INFO,
                "capabilities": {"tools": {}},
            },
        }
        print(f"Sending initialize response: {json.dumps(response)}", file=sys.stderr, flush=True)
        return response

    if method == "notifications/initialized":
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        try:
            result = call_tool(params["name"], params.get("arguments"))
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(result, indent=2, sort_keys=True),
                        }
                    ]
                },
            }
        except Exception as err:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": str(err)}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


def main() -> int:

    if sys.stdin.isatty():
        print(
            "shortcut_mcp_server.py is an MCP stdio server. Start it from an MCP client instead of running it directly.",
            file=sys.stderr,
        )
        return 1

    try:
        while True:
            message = read_message()
            if message is None:
                return 0
            response = handle_request(message)
            if response is not None:
                write_message(response)

    except RuntimeError as err:
        print(f"FATAL: {str(err)}", file=sys.stderr, flush=True)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
