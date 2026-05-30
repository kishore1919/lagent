import sys
import os
import subprocess

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "http"
    if mode == "mcp":
        here = os.path.dirname(os.path.abspath(__file__))
        mcp_path = os.path.join(here, "mcp_server.py")
        os.execv(sys.executable, [sys.executable, mcp_path])
    else:
        from http_server import main
        main()
