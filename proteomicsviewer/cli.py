"""
Pro-ker Proteomics Viewer CLI — launch the viewer from the command line.

Usage:
    proker                      # start on default port 8050
    proker data.txt             # start and auto-load a file
    proker --port 9000          # start on a custom port
    proker --no-browser         # start without opening the browser
"""

import argparse
import atexit
import json
import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

_CONFIG_DIR = Path.home() / ".proteomicsviewer"
_LOCK_FILE = _CONFIG_DIR / "server.lock"


# ── Fast instance detection ────────────────────────────────────────
def _pid_alive(pid):
    """Check whether a process with *pid* exists."""
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, pid)  # SYNCHRONIZE
        if handle:
            kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


def _http_check(host, port, timeout=0.5):
    """Quick GET /health; returns True only if our server answers."""
    try:
        import urllib.request
        url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/health"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read()).get("status") == "ok"
    except Exception:
        return False


def _check_existing_server(host, port):
    """Return the URL of an already-running server, or None."""
    try:
        if _LOCK_FILE.exists():
            data = json.loads(_LOCK_FILE.read_text())
            lock_host = data.get("host", "127.0.0.1")
            lock_port = data.get("port", 8050)
            lock_pid = data.get("pid")
            if lock_pid and _pid_alive(lock_pid) and _http_check(lock_host, lock_port):
                h = "localhost" if lock_host in ("0.0.0.0", "127.0.0.1") else lock_host
                return f"http://{h}:{lock_port}"
            _LOCK_FILE.unlink(missing_ok=True)
    except Exception:
        pass

    if _http_check(host, port):
        h = "localhost" if host in ("0.0.0.0", "127.0.0.1") else host
        return f"http://{h}:{port}"

    return None


# ── Lock file helpers ──────────────────────────────────────────────
def _write_lock(host, port):
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _LOCK_FILE.write_text(json.dumps({"host": host, "port": port, "pid": os.getpid()}))
    except Exception:
        pass


def _remove_lock():
    try:
        if _LOCK_FILE.exists():
            data = json.loads(_LOCK_FILE.read_text())
            if data.get("pid") == os.getpid():
                _LOCK_FILE.unlink()
    except Exception:
        pass


# ── Browser opener ─────────────────────────────────────────────────
def _open_when_ready(url, timeout=10):
    """Poll the health endpoint and open the browser once server responds."""
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


# ── Entry point ───────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="proker",
        description="Pro-ker Proteomics Viewer — interactive proteomics data visualization",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="Path to a proteinGroups.txt file to auto-load")
    parser.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser")
    args = parser.parse_args()

    # ── Single-instance check ────────────────────────────────────
    existing = _check_existing_server(args.host, args.port)
    if existing:
        if not args.no_browser:
            webbrowser.open(existing)
        return 0

    # Store file path for auto-load
    if args.file:
        filepath = Path(args.file).resolve()
        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            return 1
        os.environ["PROTVIEW_AUTOLOAD"] = str(filepath)

    url = f"http://{'localhost' if args.host in ('0.0.0.0',) else args.host}:{args.port}"

    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    # ── Heavy imports ────────────────────────────────────────────
    backend_dir = os.path.join(os.path.dirname(__file__), "server")
    sys.path.insert(0, backend_dir)
    os.environ["PROTVIEW_AUTO_SHUTDOWN"] = "1"

    from proteomicsviewer.server.main import app  # noqa: E402

    _write_lock(args.host, args.port)
    atexit.register(_remove_lock)

    # ── Start server ─────────────────────────────────────────────
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0
