"""Tool registrations and system-level logic for the Lagent system-debugger MCP server."""

import datetime
import os
import platform
import socket
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil
import requests
from fastmcp import FastMCP

# Default log path used when callers do not provide one.
DEFAULT_LOG_PATH = "/var/log/syslog"
DEFAULT_MAX_READ_BYTES = 65536
MAX_LINES = 1000
MAX_PROCESS_LIMIT = 100


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


def _bounded_int(
    value: int | None, default: int, min_value: int, max_value: int
) -> int:
    """Return an integer constrained to a safe inclusive range."""
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(min_value, min(parsed, max_value))


def _command_available(name: str) -> bool:
    """Return whether a command is available on PATH."""
    return shutil.which(name) is not None


def _read_text_limited(path: str, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
    """Read a text file up to max_bytes, reporting if content was truncated."""
    limit = _bounded_int(max_bytes, DEFAULT_MAX_READ_BYTES, 1, 5_000_000)
    file_path = Path(path)
    if not file_path.is_file():
        return f"Error: {path} not found."

    try:
        with file_path.open("rb") as f:
            data = f.read(limit + 1)
    except Exception as e:
        return f"Error: {e}"

    truncated = len(data) > limit
    text = data[:limit].decode("utf-8", errors="replace")
    if truncated:
        text += f"\n\n[truncated after {limit} bytes]"
    return text if text else "(no output)"


def _format_process_table(processes: list[dict[str, object]]) -> str:
    """Format process info dictionaries as a compact table."""
    lines = [f"{'PID':>7} {'NAME':<30} {'CPU%':>7} {'MEM%':>7}", "-" * 56]
    for info in processes:
        lines.append(
            f"{info.get('pid', '?'):>7} "
            f"{str(info.get('name') or '?')[:30]:<30} "
            f"{float(info.get('cpu_percent') or 0):>7.1f} "
            f"{float(info.get('memory_percent') or 0):>7.1f}"
        )
    return "\n".join(lines)


def _process_infos() -> list[dict[str, object]]:
    """Collect process information while tolerating short-lived processes."""
    infos: list[dict[str, object]] = []
    attrs = ["pid", "name", "cpu_percent", "memory_percent"]
    for proc in psutil.process_iter(attrs):
        try:
            infos.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return infos


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
    def safe_read_file(path: str, max_bytes: int = DEFAULT_MAX_READ_BYTES) -> str:
        """Read a bounded amount of text from a file.

        Args:
            path: Absolute or relative path to the file.
            max_bytes: Maximum number of bytes to read. Defaults to 65536.

        Returns:
            The file contents up to the requested limit, or an error message.
        """
        return _read_text_limited(path, max_bytes)

    @mcp.tool()
    def tail_file(path: str, lines: int = 100) -> str:
        """Read the last lines of a file.

        Args:
            path: Absolute or relative path to the file.
            lines: Number of recent lines to fetch. Defaults to 100.

        Returns:
            The most recent lines from the file, or an error message.
        """
        lines = _bounded_int(lines, 100, 1, MAX_LINES)
        return _run(["tail", "-n", str(lines), path])

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
    def inode_usage() -> str:
        """Show inode usage across all mounted filesystems.

        Returns:
            Human-readable inode usage summary from ``df -ih``.
        """
        return _run(["df", "-ih"])

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
        limit = _bounded_int(limit, 20, 1, MAX_PROCESS_LIMIT)
        for proc in psutil.process_iter():
            try:
                proc.cpu_percent(interval=None)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        time.sleep(0.2)
        procs = sorted(
            _process_infos(),
            key=lambda info: float(info.get("cpu_percent") or 0),
            reverse=True,
        )[:limit]
        return _format_process_table(procs)

    @mcp.tool()
    def top_memory_processes(limit: int = 20) -> str:
        """List the top processes sorted by memory usage.

        Args:
            limit: Maximum number of processes to return. Defaults to 20.

        Returns:
            A formatted table with PID, name, CPU%, and memory%.
        """
        limit = _bounded_int(limit, 20, 1, MAX_PROCESS_LIMIT)
        procs = sorted(
            _process_infos(),
            key=lambda info: float(info.get("memory_percent") or 0),
            reverse=True,
        )[:limit]
        return _format_process_table(procs)

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
        lines = _bounded_int(lines, 50, 1, MAX_LINES)
        if _command_available("journalctl"):
            return _run(["journalctl", "-n", str(lines), "--no-pager"])
        return _run(["tail", "-n", str(lines), "/var/log/syslog"])

    @mcp.tool()
    def service_logs(service: str, lines: int = 100) -> str:
        """Retrieve recent logs for a systemd service.

        Args:
            service: Name of the systemd service to inspect.
            lines: Number of recent log lines to fetch. Defaults to 100.

        Returns:
            Recent service log entries, or an error message.
        """
        lines = _bounded_int(lines, 100, 1, MAX_LINES)
        if not _command_available("journalctl"):
            return "Error: command 'journalctl' not found on this system."
        return _run(["journalctl", "-u", service, "-n", str(lines), "--no-pager"])

    @mcp.tool()
    def network_info() -> str:
        """Display network interfaces and IP addresses.

        Uses ``ip -brief addr`` when available, with ``ifconfig`` as a
        fallback for systems where ``ip`` is missing (e.g., older Debian).

        Returns:
            A summary of network interface status.
        """
        if _command_available("ip"):
            out = _run(["ip", "-brief", "addr"])
            if not out.startswith("[exit "):
                return out
        if _command_available("ifconfig"):
            return _run(["ifconfig"])
        return "Error: neither 'ip' nor 'ifconfig' is available on this system."

    @mcp.tool()
    def port_listeners() -> str:
        """Show listening TCP and UDP ports.

        Returns:
            Listener table from ``ss -tulpn``, or an error if unavailable.
        """
        if not _command_available("ss"):
            return "Error: command 'ss' not found on this system."
        return _run(["ss", "-tulpn"])

    @mcp.tool()
    def dns_lookup(hostname: str) -> str:
        """Resolve a hostname using the system resolver.

        Args:
            hostname: DNS name or address to resolve.

        Returns:
            Resolved addresses grouped by unique IP.
        """
        try:
            results = socket.getaddrinfo(hostname, None)
        except socket.gaierror as e:
            return f"Error: {e}"

        addresses = sorted({result[4][0] for result in results})
        return "\n".join(addresses) if addresses else "(no output)"

    @mcp.tool()
    def http_check(url: str, timeout: float = 5.0) -> str:
        """Check an HTTP URL and report status, latency, and final URL.

        Args:
            url: HTTP or HTTPS URL to request.
            timeout: Request timeout in seconds. Defaults to 5.0.

        Returns:
            A compact HTTP check summary, or an error message.
        """
        try:
            timeout = max(0.1, min(float(timeout), 30.0))
        except (TypeError, ValueError):
            timeout = 5.0

        started = time.perf_counter()
        try:
            response = requests.get(
                url, timeout=timeout, allow_redirects=True, stream=True
            )
        except requests.RequestException as e:
            return f"Error: {e}"
        try:
            elapsed_ms = (time.perf_counter() - started) * 1000
            content_type = response.headers.get("content-type", "(none)")
            return (
                f"Status: {response.status_code}\n"
                f"Elapsed: {elapsed_ms:.1f} ms\n"
                f"Final URL: {response.url}\n"
                f"Content-Type: {content_type}"
            )
        finally:
            response.close()

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
    def environment_info() -> str:
        """Report operating system and runtime environment details.

        Returns:
            OS, kernel, hostname, Python, container hints, and command availability.
        """
        os_release = _read_text_limited("/etc/os-release", 4096)
        if os_release.startswith("Error:"):
            os_release = platform.platform()

        container_hints = []
        if os.path.exists("/.dockerenv"):
            container_hints.append("/.dockerenv present")
        cgroup = _read_text_limited("/proc/1/cgroup", 8192)
        if not cgroup.startswith("Error:") and any(
            token in cgroup.lower() for token in ("docker", "containerd", "kubepods")
        ):
            container_hints.append("container cgroup detected")

        commands = ["journalctl", "systemctl", "ip", "ifconfig", "ss", "df", "tail"]
        command_lines = [
            f"  {cmd}: {'yes' if _command_available(cmd) else 'no'}"
            for cmd in commands
        ]

        lines = [
            f"Hostname: {socket.gethostname()}",
            f"Kernel: {platform.release()}",
            f"Platform: {platform.platform()}",
            f"Python: {sys.version.split()[0]}",
            "Container: "
            + (", ".join(container_hints) if container_hints else "not detected"),
            "Commands:",
            *command_lines,
            "OS Release:",
            os_release.strip(),
        ]
        return "\n".join(lines)

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
        lines = _bounded_int(lines, 20, 1, MAX_LINES)
        if os.path.isfile(path):
            return _run(["grep", "-i", "-m", str(lines), pattern, path])
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
