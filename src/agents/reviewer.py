"""Reviewer subagent specification."""

from typing import Any

from deepagents.backends.protocol import BackendProtocol

from agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from prompts import load_prompt


def create_reviewer_subagent(model: Any, backend: BackendProtocol) -> dict[str, Any]:
    """Return the isolated read-only reviewer."""
    return {
        "name": "reviewer",
        "description": "Independently reviews code and returns actionable findings.",
        "model": model,
        "system_prompt": load_prompt("reviewer"),
        "middleware": [filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/reviewer"],
    }
