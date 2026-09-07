"""Programmer subagent specification."""

from typing import Any

from deepagents.backends.protocol import BackendProtocol

from agents.config import WRITE_WITH_APPROVAL_PERMISSIONS, filesystem_middleware
from prompts import load_prompt


def create_programmer_subagent(model: Any, backend: BackendProtocol) -> dict[str, Any]:
    """Return the isolated specialist that is allowed to change code."""
    return {
        "name": "programmer",
        "description": "Implements approved code changes and reports changed files.",
        "model": model,
        "system_prompt": load_prompt("programmer"),
        "middleware": [
            filesystem_middleware(
                backend,
                ["ls", "read_file", "glob", "grep", "write_file", "edit_file", "delete"],
                WRITE_WITH_APPROVAL_PERMISSIONS,
            )
        ],
        "permissions": WRITE_WITH_APPROVAL_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/programmer"],
    }
