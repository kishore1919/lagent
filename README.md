# Lagent - Linux System Debugger Agent

Lagent is an AI-powered system debugging agent designed specifically for **Linux** environments. It uses the Model Context Protocol (MCP) to provide a suite of tools for inspecting system health, logs, network status, and processes.

## Features

- **Linux-Only Support**: Optimized for Linux systems, utilizing native tools like `journalctl`, `ip`, `systemctl`, `df`, and `psutil`.
- **HTTP/SSE Transport**: The MCP server and Agent API communicate over HTTP using Server-Sent Events (SSE).
- **FastAPI & Uvicorn**: Built on modern, high-performance Python web frameworks.
- **AI-Powered Diagnosis**: Integrates with LLMs (via OpenRouter) to analyze tool outputs and provide actionable system diagnoses.

## Architecture

1.  **MCP Server**: Hosts the system debugging tools (read files, list directories, check services, etc.) over an SSE endpoint.
2.  **Agent API**: A FastAPI server that orchestrates the LLM and the MCP tools to solve natural language debug requests.

## Prerequisites

- Python 3.10+
- A Linux environment (Ubuntu, Debian, CentOS, etc.)
- `psutil` and `fastmcp` libraries.

## Setup

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd lagent
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**:
    Create a `.env` file based on `.env.example`:
    ```bash
    OPENROUTER_API_KEY=your_api_key_here
    OPENROUTER_MODEL=openai/gpt-4o-mini
    MCP_HOST=0.0.0.0
    MCP_PORT=9000
    ```

## Running the Project

### 1. Start the MCP Server
In one terminal, start the MCP server using SSE transport:
```bash
python main.py mcp
```
By default, this runs on `http://0.0.0.0:9001`.

### 3. Start with Docker (Recommended)
You can run both the MCP server and the Agent API using Docker Compose:
```bash
docker-compose up --build
```
This will start:
- **Agent API**: `http://localhost:9000`
- **MCP Server**: `http://localhost:9001`

Note: When running in Docker, the agent will inspect the **container's** environment, not the host's, unless you mount host volumes (e.g., `-v /:/host:ro`).

## API Usage

### Agent Endpoint
**POST** `/agent`
```json
{
  "prompt": "Check if the nginx service is running and show me the last 5 lines of the syslog."
}
```

### Health Check
**GET** `/health`

### List Tools
**GET** `/tools`

## Tools Available
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
