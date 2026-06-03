# Lagent - Linux System Debugger (MCP Server)

Lagent is a high-performance **Model Context Protocol (MCP)** server named `system-debugger`, designed for **Linux** environments. It provides 20 specialized tools for inspecting system health, logs, network status, files, and processes over FastMCP streamable HTTP.

## Features

- **Linux-Native**: Leverages native tools like `journalctl`, `ip`, `systemctl`, `df`, and `psutil` for accurate system inspection.
- **MCP Streamable HTTP**: Built on the latest FastMCP framework, providing a high-performance, streamable HTTP transport for MCP clients.
- **Gradio Test UI**: Includes a built-in web interface for testing and interacting with tools without a full MCP client.
- **Docker Ready**: Multi-stage Docker build for minimal footprint and easy deployment.

## Prerequisites

- Python 3.10+
- A Linux environment (required for native system-level tools).
- Docker & Docker Compose (optional).

## Setup & Deployment

### 1. Run with Docker Compose (Recommended)
```bash
docker-compose up --build
```
The MCP server will be accessible at: `http://localhost:9001/mcp`

### 2. Run Locally
**Install dependencies:**
```bash
pip install -r requirements.txt
```

**Start the server:**
```bash
python server.py
```
By default, the server binds to `0.0.0.0:9001` and serves the MCP protocol at `/mcp`.

## How to use with MCP Clients

Connect your MCP client (e.g., Claude Desktop, MCP Inspector) to:
- **Transport**: Streamable HTTP
- **URL**: `http://localhost:9001/mcp`

## Testing with Gradio UI

A web interface is provided for manual testing and tool inspection.

1. Ensure the MCP server is running: `python server.py`
2. Launch the Gradio UI: `python gradio_ui.py`
3. Open the provided local URL in your browser. You can select tools, enter JSON arguments, and view real-time output.

## Tools Provided

### 📂 File & Directory
- `read_file(path)`: Read the contents of a file.
- `safe_read_file(path, max_bytes=65536)`: Read a bounded amount of text from a file (safely handles large files).
- `tail_file(path, lines=100)`: Read the last lines of a file.
- `list_directory(path=".")`: List files and directories with detailed metadata.

### 📊 System Health & Performance
- `cpu_info()`: Report CPU count, usage percentage, and load averages.
- `memory_info()`: Retrieve detailed RAM and swap usage statistics.
- `disk_usage()`: Show disk space usage across all mounted filesystems.
- `inode_usage()`: Show inode usage (important for filesystem health).
- `uptime()`: Show system boot time and total uptime duration.
- `environment_info()`: Detailed report on OS, kernel, Python, and command availability.

### ⚙️ Processes & Services
- `running_processes(limit=20)`: List top processes sorted by CPU usage.
- `top_memory_processes(limit=20)`: List top processes sorted by memory usage.
- `check_service(service)`: Check the full status of a `systemd` service.
- `service_logs(service, lines=100)`: Retrieve recent logs for a specific `systemd` service.

### 📝 Logs & Inspection
- `system_logs(lines=50)`: Retrieve recent system logs via `journalctl` (or `/var/log/syslog` fallback).
- `grep_log(pattern, path="/var/log/syslog", lines=20)`: Search for a pattern in logs with line limiting.

### 🌐 Network
- `network_info()`: Display network interfaces and IP addresses.
- `port_listeners()`: Show all listening TCP and UDP ports.
- `dns_lookup(hostname)`: Resolve a hostname using the system resolver.
- `http_check(url, timeout=5.0)`: Check URL status, latency, and headers.

## 📦 Container Considerations

When running inside Docker, Lagent has restricted visibility into the host system by default. To allow full inspection of the host:

- **Logs/Journal**: Mount `/var/log` and `/run/systemd/journal` into the container.
- **Processes**: Use `--pid=host` in your docker run command or `pid: host` in `docker-compose.yml`.
- **Network**: Use `--network=host` or `network_mode: host`.

## 🛡️ Security

Lagent is a powerful debugging tool that can read sensitive files and logs. 
- **Recommendation**: Do not expose the MCP port (`9001`) to the public internet without a reverse proxy and authentication.
- **Access Control**: By default, the server listens on all interfaces (`0.0.0.0`). Set `MCP_HOST=127.0.0.1` for local-only access.

## Environment Variables

| Variable   | Default   | Description               |
|------------|-----------|---------------------------|
| `MCP_HOST` | `0.0.0.0` | Host interface to bind to |
| `MCP_PORT` | `9001`    | Port to listen on         |

---
Lagent is built with [FastMCP](https://github.com/jlowin/fastmcp).
