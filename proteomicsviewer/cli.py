"""
Pro-ker Proteomics Analysis CLI — launch the viewer from the command line.

Usage:
    proker                      # start on default port 8050
    proker data.txt             # start and auto-load a file
    proker --port 9000          # start on a custom port
    proker --no-browser         # start without opening the browser
    proker --install            # create a desktop shortcut
    proker --update             # check for updates and install if available
    proker --no-update          # skip the automatic update check
"""

import argparse
import atexit
import json
import os
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

_CONFIG_DIR = Path.home() / ".proker"
_LOCK_FILE = _CONFIG_DIR / "server.lock"
_FIRST_RUN_MARKER = _CONFIG_DIR / ".shortcut_prompted"
_UPDATE_CHECK_FILE = _CONFIG_DIR / ".last_update_check"
_VERSION_MARKER = _CONFIG_DIR / ".installed_version"

_UPDATE_CHECK_INTERVAL = 3600  # 1 hour


# ── Welcome message ──────────────────────────────────────────────
def _show_welcome_if_new():
    ver = _get_installed_version()
    try:
        prev = _VERSION_MARKER.read_text().strip() if _VERSION_MARKER.exists() else None
    except Exception:
        prev = None

    if prev == ver:
        return

    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _VERSION_MARKER.write_text(ver)
    except Exception:
        pass

    try:
        if sys.stdout is None:
            return
        sys.stdout.write('')
    except Exception:
        return

    is_upgrade = prev is not None
    print()
    print(f"  {'=' * 44}")
    if is_upgrade:
        print(f"    Pro-ker Proteomics Analysis updated to v{ver}")
    else:
        print(f"    Pro-ker Proteomics Analysis v{ver} installed")
    print(f"  {'=' * 44}")
    print()
    if not is_upgrade:
        print("  Supported formats:")
        print("    MaxQuant proteinGroups.txt (tab-separated)")
        print()
        print("  Quick start:")
        print("    - Upload a proteinGroups.txt file")
        print("    - Assign samples to groups")
        print("    - Configure processing options")
        print("    - Add visualizations to the canvas")
        print()
    print("  Commands:")
    print("    proker                Launch the viewer")
    print("    proker file.txt       Load a file on start")
    print("    proker --update       Check for updates")
    print("    proker --install      Create a desktop shortcut")
    print("    proker --version      Show installed version")
    print()


# ── Auto-update ──────────────────────────────────────────────────
def _get_installed_version():
    try:
        from proteomicsviewer import __version__
        return __version__
    except Exception:
        return "0.0.0"


def _get_pypi_version():
    try:
        import urllib.request
        url = "https://pypi.org/pypi/proker/json"
        with urllib.request.urlopen(url, timeout=3) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def _version_tuple(v):
    try:
        return tuple(int(x) for x in v.split(".")[:3])
    except Exception:
        return (0, 0, 0)


def _should_check_update():
    try:
        if _UPDATE_CHECK_FILE.exists():
            last = float(_UPDATE_CHECK_FILE.read_text().strip())
            return (time.time() - last) > _UPDATE_CHECK_INTERVAL
    except Exception:
        pass
    return True


def _record_update_check():
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _UPDATE_CHECK_FILE.write_text(str(time.time()))
    except Exception:
        pass


def _do_upgrade():
    cmds = [
        [sys.executable, "-m", "pip", "install", "--upgrade", "proker"],
        [sys.executable, "-m", "pip", "install", "--upgrade", "--user", "proker"],
    ]
    last_err = None
    for cmd in cmds:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if result.returncode == 0:
                return True
            last_err = result.stderr.strip()[:200]
        except Exception as e:
            last_err = str(e)
    if last_err:
        _log(f"  pip failed: {last_err}")
    return False


def _log(msg):
    try:
        print(msg)
    except Exception:
        pass
    try:
        log = _CONFIG_DIR / "update.log"
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(log, "a") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except Exception:
        pass


def check_and_update(force=False):
    if not force and not _should_check_update():
        return ('skip', None)

    _record_update_check()
    installed = _get_installed_version()
    latest = _get_pypi_version()

    if latest is None:
        return ('skip', None)
    if _version_tuple(latest) <= _version_tuple(installed):
        return ('current', None)

    _log(f"  Updating Pro-ker: {installed} -> {latest} ...")
    if _do_upgrade():
        _log(f"  Updated to {latest}.")
        return ('updated', latest)
    else:
        _log(f"  Update failed (retry with: proker --update)")
        return ('failed', latest)


def _check_update_with_prompt():
    try:
        _record_update_check()
        installed = _get_installed_version()
        latest = _get_pypi_version()

        if latest is None or _version_tuple(latest) <= _version_tuple(installed):
            return

        has_terminal = False
        try:
            if sys.stdout is not None and hasattr(sys.stdout, 'write'):
                sys.stdout.write('')
                has_terminal = True
        except Exception:
            pass

        should_update = False

        if has_terminal:
            try:
                print(f"\n  Update available: {installed} -> {latest}")
                answer = input("  Install update now? [Y/n]: ").strip()
                should_update = answer.lower() != 'n'
            except (EOFError, OSError):
                should_update = _tk_update_prompt(installed, latest)
        else:
            should_update = _tk_update_prompt(installed, latest)

        if should_update:
            _log(f"  Updating Pro-ker: {installed} -> {latest} ...")
            if _do_upgrade():
                _log(f"  Updated to {latest}.")
                if has_terminal:
                    print(f"\n  Please run 'proker' again to launch the new version.\n")
                    sys.exit(0)
                else:
                    try:
                        import tkinter as tk
                        from tkinter import messagebox
                        root = tk.Tk(); root.withdraw()
                        messagebox.showinfo(
                            "Pro-ker",
                            f"Updated to v{latest}.\n\nThe viewer will now relaunch."
                        )
                        root.destroy()
                    except Exception:
                        pass
                    subprocess.Popen([sys.executable, "-m", "proteomicsviewer", "--no-update"])
                    sys.exit(0)
            else:
                _log(f"  Update failed. Retry with: proker --update")
    except Exception:
        pass


def _tk_update_prompt(installed, latest):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        answer = messagebox.askyesno(
            "Pro-ker Update",
            f"A new version is available: {installed} -> {latest}\n\n"
            f"Install the update now?",
        )
        root.destroy()
        return answer
    except Exception:
        return False


# ── Instance detection ───────────────────────────────────────────
def _pid_alive(pid):
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x100000, False, pid)
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
    try:
        import urllib.request
        url = f"http://{'localhost' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/health"
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read()).get("status") == "ok"
    except Exception:
        return False


def _check_existing_server(host, port):
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


# ── Lock file helpers ────────────────────────────────────────────
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


# ── First-run shortcut prompt ────────────────────────────────────
def _offer_shortcut_install():
    if _FIRST_RUN_MARKER.exists():
        return
    try:
        _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        _FIRST_RUN_MARKER.write_text("prompted")
    except Exception:
        return

    try:
        answer = input("  Create a desktop shortcut? [Y/n]: ").strip()
        if answer.lower() != 'n':
            try:
                from proteomicsviewer.install_shortcut import main as install_main
                install_main()
            except ImportError:
                print("  Shortcut creation requires tkinter.")
                print("  You can create a shortcut later with: proker --install")
            except Exception as e:
                print(f"  Shortcut creation failed: {e}")
                print("  You can try again later with: proker --install")
            print()  # blank line before server starts
        return
    except (EOFError, OSError, KeyboardInterrupt):
        print()
        pass

    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        answer = messagebox.askyesno(
            "Pro-ker",
            "Would you like to create a desktop shortcut?\n\n"
            "You can also do this later with:  proker --install",
        )
        root.destroy()
        if answer:
            from proteomicsviewer.install_shortcut import main as install_main
            install_main()
    except Exception:
        pass


# ── Browser opener ───────────────────────────────────────────────
def _open_when_ready(url, timeout=10):
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(f"{url}/health", timeout=0.5)
            break
        except Exception:
            time.sleep(0.2)
    webbrowser.open(url)


# ── Entry point ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="proker",
        description="Pro-ker Proteomics Analysis — interactive proteomics data visualization",
    )
    parser.add_argument("file", nargs="?", default=None,
                        help="Path to a proteinGroups.txt file to auto-load")
    parser.add_argument("--port", type=int, default=8050, help="Port (default: 8050)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open the browser")
    parser.add_argument("--install", action="store_true", help="Create a desktop shortcut")
    parser.add_argument("--update", action="store_true", help="Check for updates now")
    parser.add_argument("--no-update", action="store_true", help="Skip automatic update check")
    parser.add_argument("--version", action="store_true", help="Show version and exit")
    args = parser.parse_args()

    if args.version:
        print(f"Pro-ker Proteomics Analysis {_get_installed_version()}")
        return 0

    if args.install:
        try:
            from proteomicsviewer.install_shortcut import main as install_main
            install_main()
        except ImportError:
            print("  Shortcut creation requires tkinter.")
            print("  Install it with: conda install tk  (or)  sudo apt install python3-tk")
        except Exception as e:
            print(f"  Shortcut creation failed: {e}")
        return 0

    # Manual update command
    if args.update:
        status, ver = check_and_update(force=True)
        if status == 'updated':
            print(f"  Pro-ker updated to {ver}.")
            print(f"  Run 'proker' to launch the new version.")
        elif status == 'failed':
            print(f"  Update to {ver} failed.")
            print(f"  Check ~/.proker/update.log for details.")
            print(f"  Or update manually: pip install --upgrade proker")
        elif status == 'skip':
            print(f"  Could not reach PyPI. Check your internet connection.")
        else:
            print(f"  Pro-ker {_get_installed_version()} is up to date.")
        return 0

    # Welcome message on first run / upgrade
    _show_welcome_if_new()

    # Pre-launch update check
    has_terminal = False
    try:
        if sys.stdout is not None and hasattr(sys.stdout, 'write'):
            sys.stdout.write('')
            has_terminal = True
    except Exception:
        pass

    if not args.no_update and has_terminal:
        _check_update_with_prompt()

    # Single-instance check
    existing = _check_existing_server(args.host, args.port)
    if existing:
        if not args.no_browser:
            webbrowser.open(existing)
        return 0

    # First launch — offer desktop shortcut
    _offer_shortcut_install()

    # Store file path for auto-load
    if args.file:
        filepath = Path(args.file).resolve()
        if not filepath.exists():
            print(f"Error: file not found: {filepath}", file=sys.stderr)
            return 1
        os.environ["PROTVIEW_AUTOLOAD"] = str(filepath)

    url = f"http://{'localhost' if args.host in ('0.0.0.0',) else args.host}:{args.port}"

    print(f"\n  Starting Pro-ker at {url}\n")

    if not args.no_browser:
        threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()

    # Heavy imports
    backend_dir = os.path.join(os.path.dirname(__file__), "server")
    sys.path.insert(0, backend_dir)
    os.environ["PROTVIEW_AUTO_SHUTDOWN"] = "1"

    from proteomicsviewer.server.main import app  # noqa: E402

    _write_lock(args.host, args.port)
    atexit.register(_remove_lock)

    # Background update check for pythonw launches
    if not args.no_update and not has_terminal:
        def _bg_update_check():
            time.sleep(3)
            try:
                installed = _get_installed_version()
                latest = _get_pypi_version()
                if latest and _version_tuple(latest) > _version_tuple(installed):
                    _log(f"  Update available: {installed} -> {latest}. Run 'proker --update'.")
                    if _tk_update_prompt(installed, latest):
                        if _do_upgrade():
                            _log(f"  Updated to {latest}.")
                            try:
                                import tkinter as tk
                                from tkinter import messagebox
                                root = tk.Tk(); root.withdraw()
                                messagebox.showinfo("Pro-ker", f"Updated to v{latest}.\n\nRestart to use the new version.")
                                root.destroy()
                            except Exception:
                                pass
            except Exception:
                pass
        threading.Thread(target=_bg_update_check, daemon=True).start()

    # Start server
    if sys.platform == "win32":
        import asyncio
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0
