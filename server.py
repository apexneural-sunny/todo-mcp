"""
MCP Todo List Server
A FastMCP server exposing todo list operations via HTTP for n8n integration.
"""

import json
import uuid
from datetime import datetime
from typing import Optional, List
from enum import Enum

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, ConfigDict


# ──────────────────────────────────────────────
# In-memory storage (replace with DB for prod)
# ──────────────────────────────────────────────
TODOS: dict[str, dict] = {}


# ──────────────────────────────────────────────
# Enums & helpers
# ──────────────────────────────────────────────
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Status(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _todo_or_error(todo_id: str) -> dict | None:
    return TODOS.get(todo_id)


def _format_todo(t: dict) -> dict:
    return t.copy()


# ──────────────────────────────────────────────
# Input Models
# ──────────────────────────────────────────────
class CreateTodoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(..., description="Title of the todo item", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="Optional longer description")
    priority: Priority = Field(default=Priority.MEDIUM, description="Priority: low | medium | high")
    due_date: Optional[str] = Field(default=None, description="ISO 8601 due date, e.g. '2025-12-31'")
    tags: Optional[List[str]] = Field(default_factory=list, description="List of tags")


class UpdateTodoInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    todo_id: str = Field(..., description="ID of the todo to update")
    title: Optional[str] = Field(default=None, description="New title", min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, description="New description")
    priority: Optional[Priority] = Field(default=None, description="New priority")
    status: Optional[Status] = Field(default=None, description="New status: pending | in_progress | done")
    due_date: Optional[str] = Field(default=None, description="New ISO 8601 due date")
    tags: Optional[List[str]] = Field(default=None, description="Replace tags list")


class GetTodoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    todo_id: str = Field(..., description="ID of the todo to retrieve")


class DeleteTodoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    todo_id: str = Field(..., description="ID of the todo to delete")


class ListTodosInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Optional[Status] = Field(default=None, description="Filter by status")
    priority: Optional[Priority] = Field(default=None, description="Filter by priority")
    tag: Optional[str] = Field(default=None, description="Filter by tag")
    limit: int = Field(default=50, description="Max results", ge=1, le=200)
    offset: int = Field(default=0, description="Pagination offset", ge=0)


# ──────────────────────────────────────────────
# MCP Server
# ──────────────────────────────────────────────
mcp = FastMCP("todo_mcp")


# ──────────────────────────────────────────────
# Middleware: Fix Accept headers for n8n clients
# n8n doesn't send the required Accept header that
# MCP Streamable HTTP needs: "application/json, text/event-stream"
# ──────────────────────────────────────────────
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest


class AcceptHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        accept = request.headers.get("accept", "")
        if "application/json" not in accept or "text/event-stream" not in accept:
            headers = dict(request.headers)
            headers["accept"] = "application/json, text/event-stream"
            request.scope["headers"] = [
                (k.lower().encode(), v.encode()) for k, v in headers.items()
            ]
        return await call_next(request)


@mcp.custom_route("/", methods=["GET"])
async def root(request):
    """Root endpoint showing server information."""
    from starlette.responses import HTMLResponse
    
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>MCP Todo Server</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }
            h1 { color: #333; }
            .endpoint { background: #f4f4f4; padding: 10px; margin: 10px 0; border-radius: 5px; }
            code { background: #e8e8e8; padding: 2px 6px; border-radius: 3px; }
        </style>
    </head>
    <body>
        <h1>🚀 MCP Todo Server</h1>
        <p>Server is running successfully!</p>
        
        <h2>📡 MCP Endpoint</h2>
        <div class="endpoint">
            <strong>URL:</strong> <code>http://0.0.0.0:8000/mcp</code>
        </div>
        
        <h2>🛠️ Available Tools</h2>
        <ul>
            <li><code>todo_create</code> - Create a new todo</li>
            <li><code>todo_get</code> - Get a todo by ID</li>
            <li><code>todo_list</code> - List todos with filters</li>
            <li><code>todo_update</code> - Update a todo</li>
            <li><code>todo_delete</code> - Delete a todo</li>
            <li><code>todo_stats</code> - Get statistics</li>
        </ul>
        
        <h2>📖 Documentation</h2>
        <p>Connect your MCP client to <code>/mcp</code> endpoint to access the tools.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@mcp.tool(
    name="todo_create",
    annotations={
        "title": "Create Todo",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def todo_create(params: CreateTodoInput) -> str:
    """Create a new todo item.

    Args:
        params (CreateTodoInput): title, description, priority, due_date, tags

    Returns:
        str: JSON with the created todo object including its auto-generated id.
    """
    todo_id = str(uuid.uuid4())
    todo = {
        "id": todo_id,
        "title": params.title,
        "description": params.description,
        "priority": params.priority.value,
        "status": Status.PENDING.value,
        "due_date": params.due_date,
        "tags": params.tags or [],
        "created_at": _now(),
        "updated_at": _now(),
    }
    TODOS[todo_id] = todo
    return json.dumps({"success": True, "todo": _format_todo(todo)}, indent=2)


@mcp.tool(
    name="todo_get",
    annotations={
        "title": "Get Todo",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def todo_get(params: GetTodoInput) -> str:
    """Retrieve a single todo item by ID.

    Args:
        params (GetTodoInput): todo_id

    Returns:
        str: JSON with the todo object, or an error message if not found.
    """
    todo = _todo_or_error(params.todo_id)
    if not todo:
        return json.dumps({"success": False, "error": f"Todo '{params.todo_id}' not found."})
    return json.dumps({"success": True, "todo": _format_todo(todo)}, indent=2)


@mcp.tool(
    name="todo_list",
    annotations={
        "title": "List Todos",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def todo_list(params: ListTodosInput) -> str:
    """List todo items with optional filters and pagination.

    Args:
        params (ListTodosInput): status, priority, tag, limit, offset

    Returns:
        str: JSON with list of todos and pagination metadata.
    """
    items = list(TODOS.values())

    if params.status:
        items = [t for t in items if t["status"] == params.status.value]
    if params.priority:
        items = [t for t in items if t["priority"] == params.priority.value]
    if params.tag:
        items = [t for t in items if params.tag in t.get("tags", [])]

    total = len(items)
    page = items[params.offset : params.offset + params.limit]

    return json.dumps(
        {
            "success": True,
            "total": total,
            "count": len(page),
            "offset": params.offset,
            "has_more": total > params.offset + len(page),
            "todos": [_format_todo(t) for t in page],
        },
        indent=2,
    )


@mcp.tool(
    name="todo_update",
    annotations={
        "title": "Update Todo",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def todo_update(params: UpdateTodoInput) -> str:
    """Update fields of an existing todo item.

    Args:
        params (UpdateTodoInput): todo_id plus any fields to change

    Returns:
        str: JSON with updated todo object, or error if not found.
    """
    todo = _todo_or_error(params.todo_id)
    if not todo:
        return json.dumps({"success": False, "error": f"Todo '{params.todo_id}' not found."})

    if params.title is not None:
        todo["title"] = params.title
    if params.description is not None:
        todo["description"] = params.description
    if params.priority is not None:
        todo["priority"] = params.priority.value
    if params.status is not None:
        todo["status"] = params.status.value
    if params.due_date is not None:
        todo["due_date"] = params.due_date
    if params.tags is not None:
        todo["tags"] = params.tags

    todo["updated_at"] = _now()
    TODOS[params.todo_id] = todo
    return json.dumps({"success": True, "todo": _format_todo(todo)}, indent=2)


@mcp.tool(
    name="todo_delete",
    annotations={
        "title": "Delete Todo",
        "readOnlyHint": False,
        "destructiveHint": True,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def todo_delete(params: DeleteTodoInput) -> str:
    """Permanently delete a todo item.

    Args:
        params (DeleteTodoInput): todo_id

    Returns:
        str: JSON confirming deletion or error if not found.
    """
    if params.todo_id not in TODOS:
        return json.dumps({"success": False, "error": f"Todo '{params.todo_id}' not found."})
    del TODOS[params.todo_id]
    return json.dumps({"success": True, "deleted_id": params.todo_id})


@mcp.tool(
    name="todo_stats",
    annotations={
        "title": "Todo Statistics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def todo_stats() -> str:
    """Get a summary of all todos grouped by status and priority.

    Returns:
        str: JSON with counts per status and priority.
    """
    stats: dict = {
        "total": len(TODOS),
        "by_status": {s.value: 0 for s in Status},
        "by_priority": {p.value: 0 for p in Priority},
    }
    for t in TODOS.values():
        stats["by_status"][t["status"]] = stats["by_status"].get(t["status"], 0) + 1
        stats["by_priority"][t["priority"]] = stats["by_priority"].get(t["priority"], 0) + 1

    return json.dumps({"success": True, "stats": stats}, indent=2)


# ──────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="MCP Todo List Server")
    parser.add_argument("--transport", default="streamable_http", choices=["stdio", "streamable_http"])
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    if args.transport == "streamable_http":
        print(f"🚀  MCP Todo server running on http://{args.host}:{args.port}/mcp")
        # Build the Starlette app and attach the middleware
        app = mcp.streamable_http_app()
        app.add_middleware(AcceptHeaderMiddleware)
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            forwarded_allow_ips="*",   # Trust proxy, fixes "Invalid Host header"
            proxy_headers=True,
        )
    else:
        mcp.run()