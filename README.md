# Lagent - Linux System Debugger (MCP Server)

Lagent is a high-performance **Model Context Protocol (MCP)** server named `system-debugger`, designed for **Linux** environments. It provides 11 tools for inspecting system health, logs, network status, and processes over HTTP (SSE).

## Features

- **Linux-Only**: Optimized for Linux systems using native tools (`journalctl`, `ip`, `systemctl`, `df`, `psutil`).
- **MCP HTTP/SSE**: Implements the latest MCP standard over HTTP (Server-Sent Events).
- **FastMCP**: Built with the `fastmcp` framework for high performance and low latency.
- **Docker Ready**: Multi-stage Docker build for a minimal footprint.

## Prerequisites

- Python 3.10+
- A Linux environment (required for system-level tools).
- Docker & Docker Compose (optional).

## Setup & Deployment

### 1. Run with Docker Compose (Recommended)
```bash
docker-compose up --build
```
The MCP server will be accessible at: `http://localhost:9001` (ASGI/Uvicorn)

### 2. Run Locally
**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Start the server (via Uvicorn):**
```bash
uvicorn server:app --host 0.0.0.0 --port 9001
```
Or simply:
```bash
python server.py
```
By default, this runs on `http://0.0.0.0:9001`.

## How to use with MCP Clients

Connect your MCP client (like Claude Desktop) to the SSE endpoint:
- **URL**: `http://localhost:9001/sse`

## Tools Provided

### File & Directory
- `read_file(path)` — Read the contents of a file.
- `list_directory(path=".")` — List files and directories at a given path.

### System Health
- `disk_usage()` — Check disk space usage across all mounted filesystems.
- `memory_info()` — Get detailed RAM and swap usage statistics.
- `cpu_info()` — Get CPU count, usage percentage, and load average.
- `uptime()` — Show system boot time and uptime duration.

### Processes & Logs
- `running_processes(limit=20)` — List top processes sorted by CPU usage.
- `system_logs(lines=50)` — Retrieve recent system logs via `journalctl` (preferred) or `tail`.
- `grep_log(pattern, path="/var/log/syslog", lines=20)` — Search for a pattern in log files (case-insensitive).

### Network & Services
- `network_info()` — Display network interfaces and IP addresses via `ip` or `ifconfig`.
- `check_service(service)` — Check the status of a `systemd` service.

## Environment Variables

| Variable   | Default   | Description               |
|------------|-----------|---------------------------|
| `MCP_HOST` | `0.0.0.0` | Host interface to bind to |
| `MCP_PORT` | `9001`    | Port to listen on         |

Create a `.env` file based on `.env.example` to customize these settings.

## Development

| File       | Purpose                                                        |
|------------|----------------------------------------------------------------|
| `server.py` | Entry point — creates the FastMCP server and exposes the ASGI app |
| `tools.py`  | Tool registrations and all system-level logic                  |

## Dependencies

- **fastmcp** (≥2.0.0) — MCP server framework
- **fastapi** (≥0.111.0) — ASGI web framework
- **uvicorn** (≥0.30.0) — ASGI server
- **psutil** (≥5.9.0) — System and process utilities
- **python-dotenv** (≥1.0.0) — `.env` file support
- **pydantic-settings** (≥2.6.0) — Settings management
- **requests** (≥2.32.0) — HTTP client (used by MCP transport)
