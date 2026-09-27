"""Programmer subagent specification."""

from pathlib import Path

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import WRITE_WITH_APPROVAL_PERMISSIONS, filesystem_middleware
from src.prompts import load_prompt


def create_programmer_subagent(
    model: str | BaseChatModel,
    backend: BackendProtocol,
    *,
    workspace_root: str | Path = ".",
) -> SubAgent:
    """Return the isolated specialist that is allowed to change code."""
    return {
        "name": "programmer",
        "description": "Implements approved code changes and reports changed files.",
        "model": model,
        "system_prompt": load_prompt("programmer", workspace_root=workspace_root),
        "middleware": [
            filesystem_middleware(
                backend,
                [
                    "ls",
                    "read_file",
                    "glob",
                    "grep",
                    "write_file",
                    "edit_file",
                    "delete",
                ],
                WRITE_WITH_APPROVAL_PERMISSIONS,
            )
        ],
        "permissions": WRITE_WITH_APPROVAL_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/programmer"],
    }
