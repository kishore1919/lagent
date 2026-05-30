import os
import sys
from tools import make_mcp_server

def main():
    # Use environment variables for configuration if provided
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "9001"))
    
    server = make_mcp_server()
    
    print(f"Starting MCP Server on http://{host}:{port}")
    print("Transport: SSE (HTTP)")
    
    # Run using the built-in SSE transport (FastAPI/Uvicorn under the hood)
    server.run(transport="http", host=host, port=port)

if __name__ == "__main__":
    main()
