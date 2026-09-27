"""Reviewer subagent specification."""

from pathlib import Path

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from src.prompts import load_prompt


def create_reviewer_subagent(
    model: str | BaseChatModel,
    backend: BackendProtocol,
    *,
    workspace_root: str | Path = ".",
) -> SubAgent:
    """Return the isolated read-only reviewer."""
    return {
        "name": "reviewer",
        "description": "Independently reviews code and returns actionable findings.",
        "model": model,
        "system_prompt": load_prompt("reviewer", workspace_root=workspace_root),
        "middleware": [
            filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/reviewer"],
    }
