# MCP Todo List Server

A Python MCP server exposing a full todo list API over **Streamable HTTP**, ready to connect with **n8n**.

---

## 📦 Installation

```bash
pip3 install -r requirements.txt
```

---

## 🚀 Running the Server

```bash
python3 server.py
# Server starts at http://0.0.0.0:8000/mcp
```

Optional flags:
```bash
python3 server.py --port 9000           # custom port
python3 server.py --transport stdio     # for local Claude Desktop / CLI use
```

---

## 🛠️ Available Tools

| Tool | Description |
|------|-------------|
| `todo_create` | Create a new todo |
| `todo_get` | Get a todo by ID |
| `todo_list` | List todos (with filters & pagination) |
| `todo_update` | Update title, status, priority, tags, etc. |
| `todo_delete` | Delete a todo permanently |
| `todo_stats` | Get counts by status and priority |

---

## 🔗 Connecting to n8n

### Step 1 — Start the server
```bash
python3 server.py --port 8000
```
Make sure n8n can reach this host. If n8n runs in Docker, use your machine's LAN IP instead of `localhost`.

### Step 2 — Add the MCP node in n8n

1. Open your n8n workflow.
2. Add a new node → search **"MCP"** (or **"AI Tool"** depending on your n8n version).
3. Choose **MCP Client** node.

### Step 3 — Configure the MCP connection

In the MCP Client node settings:

| Field | Value |
|-------|-------|
| **Transport** | `Streamable HTTP` |
| **URL** | `http://<your-host>:8000/mcp` |
| **Authentication** | None (or add your own middleware) |

### Step 4 — Use it in an AI Agent workflow

Connect the MCP Client to an **AI Agent** node (e.g. with OpenAI or Claude):
```
Trigger → AI Agent → MCP Client (todo_mcp tools)
```

The agent will automatically discover all 6 tools and can call them naturally.

### Step 5 — Direct HTTP calls from n8n (alternative)

You can also use the **HTTP Request** node to call tools directly:

```
POST http://localhost:8000/mcp
Content-Type: application/json

{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "todo_create",
    "arguments": {
      "title": "Buy groceries",
      "priority": "high",
      "tags": ["personal"]
    }
  }
}
```

---

## 📝 Example Tool Payloads

### Create a todo
```json
{
  "title": "Write report",
  "description": "Q1 summary report",
  "priority": "high",
  "due_date": "2025-03-15",
  "tags": ["work", "urgent"]
}
```

### List pending high-priority todos
```json
{
  "status": "pending",
  "priority": "high",
  "limit": 10,
  "offset": 0
}
```

### Update status to done
```json
{
  "todo_id": "<uuid>",
  "status": "done"
}
```

---

## 🗄️ Persistent Storage (Production)

The current server uses **in-memory storage** (data is lost on restart).  
To persist data, replace `TODOS` dict with SQLite or any database:

```python
import sqlite3
# or use SQLAlchemy / aiosqlite for async support
```

---

## 🔒 Adding Authentication

Wrap the server with an API key check using a middleware layer or reverse proxy (e.g. nginx with bearer token).
