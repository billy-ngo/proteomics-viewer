"""
Pro-ker Proteomics Analysis -- desktop shortcut installer.

Opens a small Tkinter dialog letting the user choose where to place
a shortcut, then creates a platform-appropriate launcher:

  * Windows  -- .lnk  via PowerShell
  * macOS    -- .app  bundle
  * Linux    -- .desktop  file (freedesktop)
"""

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

from proteomicsviewer.icon import generate_ico, generate_png

_APP_NAME = "Pro-ker Proteomics Analysis"


def _find_exe():
    """Return the absolute path to the ``proker`` entry-point script."""
    found = shutil.which("proker")
    if found:
        return os.path.realpath(found)
    if sys.platform == "win32":
        candidate = Path(sys.executable).parent / "Scripts" / "proker.exe"
    else:
        candidate = Path(sys.executable).parent / "proker"
    if candidate.exists():
        return str(candidate)
    return None


def _default_desktop():
    """Return the user's desktop directory (best-effort)."""
    if sys.platform == "win32":
        desktop = os.path.join(os.environ.get("USERPROFILE", "~"), "Desktop")
    elif sys.platform == "darwin":
        desktop = os.path.expanduser("~/Desktop")
    else:
        try:
            result = subprocess.run(
                ["xdg-user-dir", "DESKTOP"],
                capture_output=True, text=True, timeout=5,
            )
            desktop = result.stdout.strip() or os.path.expanduser("~/Desktop")
        except Exception:
            desktop = os.path.expanduser("~/Desktop")
    return desktop


def _install_windows(target_dir):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    config_dir = Path.home() / ".proker"
    config_dir.mkdir(parents=True, exist_ok=True)

    ico_path = config_dir / "proker_icon.ico"
    ico_path.write_bytes(generate_ico())

    python_exe = sys.executable
    bat_path = config_dir / "launch_proker.bat"
    bat_path.write_text(
        '@echo off\n'
        f'start /min "" "{python_exe}" -m proteomicsviewer --no-update\n'
    )

    lnk_path = target_dir / f"{_APP_NAME}.lnk"

    ps_script = (
        "$ws = New-Object -ComObject WScript.Shell; "
        f"$s = $ws.CreateShortcut('{lnk_path}'); "
        f"$s.TargetPath = '{bat_path}'; "
        f"$s.IconLocation = '{ico_path},0'; "
        f"$s.Description = '{_APP_NAME}'; "
        f"$s.WorkingDirectory = '{Path.home()}'; "
        "$s.WindowStyle = 7; "
        "$s.Save()"
    )

    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        check=True, capture_output=True, timeout=30,
    )
    return str(lnk_path)


def _install_macos(target_dir):
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    app_dir = target_dir / f"{_APP_NAME}.app"
    contents = app_dir / "Contents"
    macos = contents / "MacOS"
    resources = contents / "Resources"

    for d in (macos, resources):
        d.mkdir(parents=True, exist_ok=True)

    python_exe = sys.executable
    launcher = macos / "launcher"
    launcher.write_text(textwrap.dedent(f"""\
        #!/usr/bin/env bash
        export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin:$PATH"
        exec "{python_exe}" -m proteomicsviewer "$@"
    """))
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    icon_set = False
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp.write(generate_png(256))
            tmp_png = tmp.name
        icns_path = resources / "icon.icns"
        subprocess.run(
            ["sips", "-s", "format", "icns", tmp_png, "--out", str(icns_path)],
            check=True, capture_output=True, timeout=30,
        )
        icon_set = True
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_png)
        except Exception:
            pass

    from proteomicsviewer import __version__
    plist = contents / "Info.plist"
    icon_entry = "<key>CFBundleIconFile</key>\n    <string>icon</string>" if icon_set else ""
    plist.write_text(textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
          "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>CFBundleName</key>
            <string>{_APP_NAME}</string>
            <key>CFBundleExecutable</key>
            <string>launcher</string>
            <key>CFBundleIdentifier</key>
            <string>com.proker.app</string>
            <key>CFBundleVersion</key>
            <string>{__version__}</string>
            <key>CFBundlePackageType</key>
            <string>APPL</string>
            {icon_entry}
        </dict>
        </plist>
    """))

    return str(app_dir)


def _install_linux(target_dir):
    exe = _find_exe()
    if not exe:
        raise RuntimeError("Cannot locate the 'proker' executable.")

    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    icon_path = target_dir / "proker.png"
    icon_path.write_bytes(generate_png(48))

    desktop_path = target_dir / "proker.desktop"
    desktop_path.write_text(textwrap.dedent(f"""\
        [Desktop Entry]
        Type=Application
        Name={_APP_NAME}
        Comment=Interactive proteomics data visualization
        Exec={exe}
        Icon={icon_path}
        Terminal=false
        Categories=Science;Biology;
    """))
    desktop_path.chmod(
        desktop_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return str(desktop_path)


def main():
    """Open a dialog, create the shortcut, and report success / failure."""
    import tkinter as tk
    from tkinter import filedialog, messagebox

    root = tk.Tk()
    root.withdraw()

    default_dir = _default_desktop()
    chosen = filedialog.askdirectory(
        title="Choose shortcut location",
        initialdir=default_dir,
    )
    if not chosen:
        root.destroy()
        return

    try:
        plat = sys.platform
        if plat == "win32":
            result = _install_windows(chosen)
        elif plat == "darwin":
            result = _install_macos(chosen)
        else:
            result = _install_linux(chosen)

        messagebox.showinfo("Shortcut Created", f"Shortcut installed:\n{result}")
    except Exception as exc:
        messagebox.showerror("Error", f"Failed to create shortcut:\n{exc}")
    finally:
        root.destroy()
