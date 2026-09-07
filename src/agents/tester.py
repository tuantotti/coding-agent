"""Tester subagent specification."""

from typing import Any

from deepagents.backends.protocol import BackendProtocol

from agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from prompts import load_prompt


def create_tester_subagent(model: Any, backend: BackendProtocol) -> dict[str, Any]:
    """Return the isolated tester with approved local-shell access."""
    return {
        "name": "tester",
        "description": "Runs approved checks and reports command outcomes without editing code.",
        "model": model,
        "system_prompt": load_prompt("tester"),
        "middleware": [
            filesystem_middleware(
                backend, [*READ_TOOLS, "execute"], READ_ONLY_PERMISSIONS
            )
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/tester"],
    }
