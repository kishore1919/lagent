"""ASGI entry point for the Lagent system-debugger MCP server."""

import os

import uvicorn
from tools import make_mcp_server

# Instantiate the FastMCP server and expose it as an ASGI app.
mcp = make_mcp_server()
app = mcp.http_app()


def main() -> None:
    """Start the MCP server using Uvicorn.

    Reads ``MCP_HOST`` and ``MCP_PORT`` from the environment (defaults to
    ``0.0.0.0:9001``) and runs the FastMCP streamable HTTP application.
    """
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "9001"))

    print(f"Starting MCP Server on http://{host}:{port}")
    print("Transport: streamable HTTP (ASGI)")

    # Uvicorn is the ASGI server that serves the FastMCP /mcp endpoint.
    uvicorn.run("server:app", host=host, port=port, log_level="info", reload=False)


if __name__ == "__main__":
    main()
