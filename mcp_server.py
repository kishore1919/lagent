import datetime
import os
import shutil
import subprocess

import psutil
from fastmcp import FastMCP

DEFAULT_LOG_PATH = "/var/log/syslog"


def _run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        if result.returncode != 0:
            return f"[exit {result.returncode}] {err or out}"
        return out if out else "(no output)"
    except FileNotFoundError:
        return f"Error: command '{cmd[0]}' not found on this system."
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 30s."
    except Exception as e:
        return f"Error: {e}"


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def read_file(path: str) -> str:
        return _run(["cat", path])

    @mcp.tool()
    def list_directory(path: str = ".") -> str:
        return _run(["ls", "-la", path])

    @mcp.tool()
    def disk_usage() -> str:
        return _run(["df", "-h"])

    @mcp.tool()
    def memory_info() -> str:
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        return (
            f"Virtual Memory:\n  Total: {vm.total / 1e9:.2f} GB\n"
            f"  Available: {vm.available / 1e9:.2f} GB\n"
            f"  Used: {vm.used / 1e9:.2f} GB ({vm.percent}%)\n"
            f"Swap:\n  Total: {sm.total / 1e9:.2f} GB\n"
            f"  Used: {sm.used / 1e9:.2f} GB\n"
            f"  Free: {sm.free / 1e9:.2f} GB"
        )

    @mcp.tool()
    def cpu_info() -> str:
        lines = [
            f"CPU Count (logical): {psutil.cpu_count()}",
            f"CPU Count (physical): {psutil.cpu_count(logical=False)}",
            f"CPU Usage: {psutil.cpu_percent(interval=1)}%",
        ]
        try:
            load = psutil.getloadavg()
            lines.append(f"Load Avg: {', '.join(f'{x:.2f}' for x in load)}")
        except AttributeError:
            pass
        return "\n".join(lines)

    @mcp.tool()
    def running_processes(limit: int = 20) -> str:
        procs = sorted(
            psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
            key=lambda p: (p.info["cpu_percent"] or 0),
            reverse=True,
        )[:limit]
        lines = [f"{'PID':>7} {'NAME':<30} {'CPU%':>7} {'MEM%':>7}", "-" * 56]
        for p in procs:
            lines.append(
                f"{p.info['pid']:>7} "
                f"{(p.info['name'] or '?'):<30} "
                f"{(p.info['cpu_percent'] or 0):>7.1f} "
                f"{(p.info['memory_percent'] or 0):>7.1f}"
            )
        return "\n".join(lines)

    @mcp.tool()
    def system_logs(lines: int = 50) -> str:
        if shutil.which("journalctl"):
            return _run(["journalctl", "-n", str(lines), "--no-pager"])
        return _run(["tail", "-n", str(lines), "/var/log/syslog"])

    @mcp.tool()
    def network_info() -> str:
        out = _run(["ip", "-brief", "addr"])
        if out.startswith("Error:"):
            out = _run(["ifconfig"])
        return out

    @mcp.tool()
    def check_service(service: str) -> str:
        return _run(["systemctl", "status", service, "--no-pager", "-l"])

    @mcp.tool()
    def uptime() -> str:
        boot = datetime.datetime.fromtimestamp(psutil.boot_time())
        delta = datetime.datetime.now() - boot
        days, rem = divmod(int(delta.total_seconds()), 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        return (
            f"System uptime: {days}d {hours}h {minutes}m\n"
            f"Boot time: {boot.strftime('%Y-%m-%d %H:%M:%S')}"
        )

    @mcp.tool()
    def grep_log(pattern: str, path: str = DEFAULT_LOG_PATH, lines: int = 20) -> str:
        if os.path.isfile(path):
            return _run(["grep", "-i", pattern, path])
        return f"Error: {path} not found."



def make_mcp_server() -> FastMCP:
    mcp = FastMCP("system-debugger")
    register_tools(mcp)
    return mcp


if __name__ == "__main__":
    import uvicorn
    mcp = make_mcp_server()
    # FastMCP.run(transport="sse") sets up a FastAPI app internally
    # We can run it directly or use uvicorn if we want more control.
    mcp.run(transport="sse", host="0.0.0.0", port=9001)
