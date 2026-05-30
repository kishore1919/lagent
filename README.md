# Lagent - Linux System Debugger (MCP Server)

Lagent is a high-performance **Model Context Protocol (MCP)** server designed for **Linux** environments. It provides a suite of tools for inspecting system health, logs, network status, and processes over HTTP (SSE).

## Features

- **Linux-Only**: Optimized for Linux systems using native tools (`journalctl`, `ip`, `systemctl`, `df`, `psutil`).
- **MCP HTTP/SSE**: Implements the latest MCP standard over HTTP (Server-Sent Events).
- **FastMCP**: Built with the `fastmcp` framework for high performance and low latency.
- **Docker Ready**: Fully containerized for easy deployment.

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
- `read_file`: Read content of a file.
- `list_directory`: List files in a directory.
- `disk_usage`: Check disk space.
- `memory_info`: Check RAM and swap usage.
- `cpu_info`: Check CPU load and usage.
- `running_processes`: List top processes by CPU usage.
- `system_logs`: Retrieve system logs via `journalctl` or `tail`.
- `network_info`: Get IP and interface status.
- `check_service`: Check status of a `systemd` service.
- `uptime`: Show system boot time and uptime.
- `grep_log`: Search for patterns in log files.

## Development

- `server.py`: Entry point that exposes the FastMCP server as an ASGI application.
- `tools.py`: Contains the tool registrations and system logic.
