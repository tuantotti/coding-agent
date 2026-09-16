"""System utility routes — local UI helpers only."""

import subprocess
from pathlib import Path

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

system_router = APIRouter(prefix="/v1/system")


@system_router.get("/find-dir")
async def find_directory(
    name: str = Query(..., min_length=1, max_length=200),
) -> JSONResponse:
    """Search for a directory by name under the user's home directory.

    Returns up to 5 matching absolute paths. Used by the UI folder-picker
    to resolve the full path after the browser's showDirectoryPicker() which
    only exposes the folder name, not the absolute path.
    """
    try:
        result = subprocess.run(
            ["find", str(Path.home()), "-maxdepth", "5", "-name", name, "-type", "d"],
            capture_output=True,
            text=True,
            timeout=6,
        )
        paths = [p for p in result.stdout.strip().splitlines() if p]
    except subprocess.TimeoutExpired:
        paths = []
    return JSONResponse({"paths": paths[:5]})
