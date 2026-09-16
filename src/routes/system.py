"""System utility routes — local UI helpers only."""

import asyncio
import shutil
import subprocess
import sys

from fastapi import APIRouter
from fastapi.responses import JSONResponse

system_router = APIRouter(prefix="/v1/system")


def _open_dir_dialog() -> str | None:
    if sys.platform == "darwin":
        # osascript is built into macOS — no extra dependencies needed
        result = subprocess.run(
            ["osascript", "-e", 'POSIX path of (choose folder with prompt "Select project folder")'],
            capture_output=True,
            text=True,
            timeout=120,
        )
        path = result.stdout.strip().rstrip("/")
        return path if path else None

    if sys.platform.startswith("linux"):
        # zenity (GNOME) or kdialog (KDE) — common on desktop Linux
        for cmd, args in [
            ("zenity", ["zenity", "--file-selection", "--directory", "--title=Select project folder"]),
            ("kdialog", ["kdialog", "--getexistingdirectory", "."]),
        ]:
            if shutil.which(cmd):
                result = subprocess.run(args, capture_output=True, text=True, timeout=120)
                path = result.stdout.strip()
                return path if path else None

    # Windows: PowerShell folder picker
    if sys.platform == "win32":
        script = (
            "Add-Type -AssemblyName System.Windows.Forms;"
            "$d = New-Object System.Windows.Forms.FolderBrowserDialog;"
            "$d.Description = 'Select project folder';"
            "if ($d.ShowDialog() -eq 'OK') { $d.SelectedPath }"
        )
        result = subprocess.run(
            ["powershell", "-Command", script],
            capture_output=True,
            text=True,
            timeout=120,
        )
        path = result.stdout.strip()
        return path if path else None

    return None


@system_router.get("/pick-dir")
async def pick_directory() -> JSONResponse:
    """Open a native OS directory picker and return the selected absolute path.

    macOS: osascript, Linux: zenity/kdialog, Windows: PowerShell FolderBrowserDialog.
    """
    loop = asyncio.get_event_loop()
    path = await loop.run_in_executor(None, _open_dir_dialog)
    return JSONResponse({"path": path})
