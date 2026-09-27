"""Requirement analyst subagent specification."""

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import (
    READ_ONLY_PERMISSIONS,
    READ_TOOLS,
    filesystem_middleware,
)
from src.prompts import load_prompt


def create_requirement_subagent(
    model: str | BaseChatModel,
    backend: BackendProtocol,
) -> SubAgent:
    """Return the read-only requirement analysis specialist."""
    return {
        "name": "requirement_analyst",
        "description": (
            "Analyzes software change requests, inspects repository context, "
            "identifies ambiguity, and produces clear testable requirements "
            "and acceptance criteria before implementation."
        ),
        "model": model,
        "system_prompt": load_prompt("requirement"),
        "middleware": [
            filesystem_middleware(
                backend,
                READ_TOOLS,
                READ_ONLY_PERMISSIONS,
            )
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": [
            "/agent_skills/common",
            "/agent_skills/requirement",
        ],
    }