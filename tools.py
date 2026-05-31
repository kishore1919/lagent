"""Tool registrations and system-level logic for the Lagent system-debugger MCP server."""

import datetime
import os
import shutil
import subprocess

import psutil
from fastmcp import FastMCP

# Default log path used when callers do not provide one.
DEFAULT_LOG_PATH = "/var/log/syslog"


def _run(cmd: list[str]) -> str:
    """Execute a shell command and capture its output.

    Args:
        cmd: Command and arguments as a list of strings.

    Returns:
        The stripped stdout on success, or a formatted error string if the
        command fails, times out, or is not found.
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, check=False
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        # Prefer stderr on non-zero exit so failures are visible to the LLM.
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
    """Register all Linux system inspection tools on the given FastMCP instance.

    Args:
        mcp: The FastMCP server instance to attach the tools to.
    """

    @mcp.tool()
    def read_file(path: str) -> str:
        """Read the contents of a file using ``cat``.

        Args:
            path: Absolute or relative path to the file.

        Returns:
            The file contents as a string, or an error message.
        """
        return _run(["cat", path])

    @mcp.tool()
    def list_directory(path: str = ".") -> str:
        """List files and directories at a given path.

        Args:
            path: Directory path to list. Defaults to the current directory.

        Returns:
            Long-format directory listing, or an error message.
        """
        return _run(["ls", "-la", path])

    @mcp.tool()
    def disk_usage() -> str:
        """Show disk space usage across all mounted filesystems.

        Returns:
            Human-readable summary from ``df -h``.
        """
        return _run(["df", "-h"])

    @mcp.tool()
    def memory_info() -> str:
        """Retrieve detailed RAM and swap usage statistics.

        Returns:
            A formatted string showing total, used, and available memory
            for both virtual memory and swap.
        """
        vm = psutil.virtual_memory()
        sm = psutil.swap_memory()
        return (
            f"Virtual Memory:\n Total: {vm.total / 1e9:.2f} GB\n"
            f" Available: {vm.available / 1e9:.2f} GB\n"
            f" Used: {vm.used / 1e9:.2f} GB ({vm.percent}%)\n"
            f"Swap:\n Total: {sm.total / 1e9:.2f} GB\n"
            f" Used: {sm.used / 1e9:.2f} GB\n"
            f" Free: {sm.free / 1e9:.2f} GB"
        )

    @mcp.tool()
    def cpu_info() -> str:
        """Report CPU count, usage percentage, and load average.

        Returns:
            A formatted summary of CPU information.
        """
        lines = [
            f"CPU Count (logical): {psutil.cpu_count()}",
            f"CPU Count (physical): {psutil.cpu_count(logical=False)}",
            # Blocking call to get a steady CPU usage sample.
            f"CPU Usage: {psutil.cpu_percent(interval=1)}%",
        ]
        # getloadavg is not available on Windows, so guard against AttributeError.
        try:
            load = psutil.getloadavg()
            lines.append(f"Load Avg: {', '.join(f'{x:.2f}' for x in load)}")
        except AttributeError:
            pass
        return "\n".join(lines)

    @mcp.tool()
    def running_processes(limit: int = 20) -> str:
        """List the top processes sorted by CPU usage.

        Args:
            limit: Maximum number of processes to return. Defaults to 20.

        Returns:
            A formatted table with PID, name, CPU%, and memory%.
        """
        procs = sorted(
            psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]),
            # Some processes return None for cpu_percent on the first sample;
            # treat those as 0 so the sort is stable.
            key=lambda p: p.info["cpu_percent"] or 0,
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
        """Retrieve recent system logs.

        Uses ``journalctl`` when available, otherwise falls back to
        ``tail`` on ``/var/log/syslog``.

        Args:
            lines: Number of recent log lines to fetch. Defaults to 50.

        Returns:
            The most recent log entries as a string.
        """
        if shutil.which("journalctl"):
            return _run(["journalctl", "-n", str(lines), "--no-pager"])
        return _run(["tail", "-n", str(lines), "/var/log/syslog"])

    @mcp.tool()
    def network_info() -> str:
        """Display network interfaces and IP addresses.

        Uses ``ip -brief addr`` when available, with ``ifconfig`` as a
        fallback for systems where ``ip`` is missing (e.g., older Debian).

        Returns:
            A summary of network interface status.
        """
        out = _run(["ip", "-brief", "addr"])
        if out.startswith("Error:"):
            out = _run(["ifconfig"])
        return out

    @mcp.tool()
    def check_service(service: str) -> str:
        """Check the status of a ``systemd`` service.

        Args:
            service: Name of the systemd service to inspect.

        Returns:
            Full status output from ``systemctl status``.
        """
        return _run(["systemctl", "status", service, "--no-pager", "-l"])

    @mcp.tool()
    def uptime() -> str:
        """Show system boot time and uptime duration.

        Returns:
            A human-readable uptime string and boot timestamp.
        """
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
        """Search for a case-insensitive pattern in a log file.

        Args:
            pattern: Regex or plain-text pattern to search for.
            path: Path to the log file. Defaults to ``/var/log/syslog``.
            lines: Maximum number of matching lines to return. Defaults to 20.

        Returns:
            Matching lines from the log file, or an error if the file is
            not found.
        """
        if os.path.isfile(path):
            return _run(["grep", "-i", pattern, path])
        return f"Error: {path} not found."


def make_mcp_server() -> FastMCP:
    """Create and configure the FastMCP server instance.

    Returns:
        A ``FastMCP`` instance named ``"system-debugger"`` with all Linux
        system inspection tools registered.
    """
    mcp = FastMCP("system-debugger")
    register_tools(mcp)
    return mcp
