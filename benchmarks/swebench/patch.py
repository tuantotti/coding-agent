"""Capture the complete working-tree delta as a SWE-bench prediction."""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path

from loguru import logger


class PatchError(RuntimeError):
    """The workspace could not be converted into a valid patch."""


@dataclass(frozen=True)
class CapturedPatch:
    """Exact patch bytes represented as strict UTF-8 and integrity metadata."""

    text: str
    sha256: str
    size_bytes: int


def capture_patch(workspace: Path, max_bytes: int) -> CapturedPatch:
    """Capture tracked and untracked changes without altering file contents."""
    logger.info("Capturing patch workspace={}", workspace)
    if max_bytes <= 0:
        raise PatchError("max_bytes must be positive.")
    primary_error: Exception | None = None
    result: subprocess.CompletedProcess[bytes] | None = None
    try:
        subprocess.run(
            ["git", "add", "--intent-to-add", "--", "."],
            cwd=workspace,
            check=True,
            capture_output=True,
            timeout=120,
        )
        result = subprocess.run(
            ["git", "diff", "--binary", "--no-ext-diff", "HEAD"],
            cwd=workspace,
            check=True,
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        primary_error = exc
    finally:
        try:
            subprocess.run(
                ["git", "reset", "--mixed", "--quiet", "HEAD"],
                cwd=workspace,
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (
            OSError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ) as cleanup_error:
            if primary_error is None:
                raise PatchError(
                    "Unable to restore the workspace index."
                ) from cleanup_error
    if primary_error is not None:
        raise PatchError("Unable to capture the workspace diff.") from primary_error
    if result is None:  # pragma: no cover - guarded by the exception branches above
        raise PatchError("Git produced no diff result.")
    raw = result.stdout
    if len(raw) > max_bytes:
        raise PatchError(f"Patch exceeds the {max_bytes}-byte limit.")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PatchError("Patch is not valid UTF-8.") from exc
    logger.info("Captured patch workspace={} bytes={}", workspace, len(raw))
    return CapturedPatch(
        text=text,
        sha256=hashlib.sha256(raw).hexdigest(),
        size_bytes=len(raw),
    )
