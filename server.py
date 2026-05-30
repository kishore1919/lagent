import os
import sys
import uvicorn
from tools import make_mcp_server

# Create the MCP server instance
mcp = make_mcp_server()

# Expose the ASGI app for uvicorn/other ASGI servers
# FastMCP.http_app() returns the underlying ASGI/FastAPI application.
app = mcp.http_app()

def main():
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "9001"))
    
    print(f"Starting MCP Server on http://{host}:{port}")
    print("Transport: HTTP/SSE (ASGI)")
    
    # Run using uvicorn directly for better control
    uvicorn.run("server:app", host=host, port=port, log_level="info", reload=False)

if __name__ == "__main__":
    main()
