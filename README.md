# lagent

Python Fast MCP + HTTP server for debugging Linux systems, powered by **FastMCP** and **OpenRouter** (via LangChain-compatible tool calling).

## Architecture

```
mcp_server.py     — stdio MCP server with 11 Linux debug tools
http_server.py    — FastAPI HTTP server that:
                     • mounts the MCP app (default at /mcp)
                     • exposes /tools   → JSON tool list for LLM clients
                     • exposes /health  → liveness/readiness check
                     • exposes /agent   → natural-language → LLM + tool execution
                     • exposes /invoke  → same as /agent
main.py           — single entry point (http by default):
                     python main.py          → HTTP server
                     python main.py mcp      → stdio MCP server
```

## Prerequisites

- Python 3.11+
- `uv` or `pip`
- OpenRouter API key

## Setup

```bash
# install dependencies
uv pip install -r requirements.txt

# configure env
cp .env.example .env
# edit .env and set OPENROUTER_API_KEY
```

Minimal `.env`:
```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini   # or any OpenRouter model with tool-use support
MCP_HOST=0.0.0.0
MCP_PORT=9000
MCP_BASE_URL=http://localhost:9000
```

## Run

```bash
# HTTP server (exposes MCP + agent endpoint)
python main.py
# or:
uvicorn http_server:app --host 0.0.0.0 --port 9000

# stdio MCP server (for direct MCP clients)
python mcp_server.py
```

## HTTP Endpoints

| Method | Path       | Description                                         |
|--------|------------|-----------------------------------------------------|
| GET    | /health    | Service health + tools count                        |
| GET    | /tools     | JSON list of tools (OpenAI function schema)         |
| POST   | /agent     | Natural-language prompt → LLM diagnosis via tools  |
| POST   | /invoke    | Alias for /agent                                    |

### Example: list tools

```bash
curl http://localhost:9000/tools
```

### Example: debug via agent

```bash
curl -X POST http://localhost:9000/agent \
  -H "Content-Type: application/json" \
  -d "{\"prompt\": \"Check my system memory usage and list top 5 memory-hungry processes.\"}"
```

## Linux Debug Tools (MCP)

| Tool            | Description                                       |
|-----------------|---------------------------------------------------|
| `read_file`     | Read file contents                                |
| `list_directory`| ls -la on a path                                  |
| `disk_usage`    | df -h                                             |
| `memory_info`   | Virtual memory + swap stats via psutil            |
| `cpu_info`      | CPU count, usage %, load averages                 |
| `running_processes` | Top processes by CPU %                          |
| `system_logs`   | journalctl or /var/log/syslog tail                |
| `network_info`  | ip/ifconfig output                                 |
| `check_service` | systemctl status of a unit                        |
| `uptime`        | System uptime + boot time                         |
| `grep_log`      | grep a log file for a pattern                     |

## Notes

- The MCP HTTP endpoint is mounted at `/mcp` (Streamable HTTP transport via FastMCP).
- Tool execution inside the agent creates a fresh `make_stdio_mcp()` per request so the tool state stays isolated and thread-safe.
- Requires a real Linux environment for system tools to return meaningful output. On Windows, most system tools will return "command not found" errors.
