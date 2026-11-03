import json
import sys
from pathlib import Path
from typing import Any, Optional

from backend.retrieval import (
    add_oral_entry as _add_oral_entry,
    get_lesson as _get_lesson,
    search_archive as _search_archive,
)

MCP_TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "name": "search_archive",
        "description": "Search archived artisan contributions by query and optional craft filter, returning matching entries with source metadata and citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query keywords or question"},
                "craft": {"type": "string", "description": "Optional craft filter (e.g., 'Blue Pottery', 'Paithani Weaving')"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "add_oral_entry",
        "description": "Validate and save a reviewed artisan contribution to the JSON archive.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "entry": {
                    "type": "object",
                    "description": "Reviewed artisan archive entry object",
                    "required": ["craft", "technique", "artisan_name", "transcript", "source_audio", "segment"],
                }
            },
            "required": ["entry"],
        },
    },
    {
        "name": "get_lesson",
        "description": "Return a structured craft lesson assembled strictly from archived artisan entries, preserving citations.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "craft": {"type": "string", "description": "Craft name"},
                "technique": {"type": "string", "description": "Optional technique filter"},
            },
            "required": ["craft"],
        },
    },
]


def list_mcp_tools() -> list[dict[str, Any]]:
    return MCP_TOOLS_SCHEMA


def invoke_mcp_tool(
    name: str,
    arguments: dict[str, Any],
    archive_path: Optional[Path] = None,
) -> Any:
    """
    Thin MCP tool dispatcher reusing backend.retrieval functions without duplicating logic.
    """
    if name == "search_archive":
        query = arguments.get("query", "")
        craft = arguments.get("craft")
        return _search_archive(query=query, craft=craft, archive_path=archive_path)

    if name == "add_oral_entry":
        entry = arguments.get("entry")
        if not isinstance(entry, dict):
            raise ValueError("Tool 'add_oral_entry' requires an 'entry' object.")
        return _add_oral_entry(entry=entry, archive_path=archive_path)

    if name == "get_lesson":
        craft = arguments.get("craft", "")
        technique = arguments.get("technique")
        return _get_lesson(craft=craft, technique=technique, archive_path=archive_path)

    raise ValueError(f"Unknown MCP tool: '{name}'")


def handle_jsonrpc_message(
    request: dict[str, Any],
    archive_path: Optional[Path] = None,
) -> dict[str, Any]:
    """Handle standard MCP JSON-RPC 2.0 requests (initialize, tools/list, tools/call)."""
    req_id = request.get("id")
    method = request.get("method")
    params = request.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "kalasetu-archive-mcp", "version": "2.0.0"},
                "capabilities": {"tools": {}},
            },
        }

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {"tools": list_mcp_tools()},
        }

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments") or {}
        try:
            output = invoke_mcp_tool(tool_name, tool_args, archive_path=archive_path)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False)}],
                    "structuredContent": output,
                    "isError": False,
                },
            }
        except Exception as exc:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                },
            }

    return {
        "jsonrpc": "2.0",
        "id": req_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main_stdio() -> None:
    """Minimal stdio MCP server loop."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            resp = handle_jsonrpc_message(req)
        except Exception as exc:
            resp = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Parse error: {exc}"},
            }
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main_stdio()
