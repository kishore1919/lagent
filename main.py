import sys

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "mcp":
        from mcp_server import make_mcp_server

        # Run MCP server on a different port or allow config
        make_mcp_server().run(transport="sse", host="0.0.0.0", port=9001)
    else:
        from http_server import main

        main()
