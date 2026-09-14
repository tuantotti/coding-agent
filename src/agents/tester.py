"""Tester subagent specification."""

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from src.prompts import load_prompt


def create_tester_subagent(
    model: str | BaseChatModel, backend: BackendProtocol
) -> SubAgent:
    """Return the isolated tester with approved local-shell access."""
    return {
        "name": "tester",
        "description": "Runs approved checks and reports their outcomes.",
        "model": model,
        "system_prompt": load_prompt("tester"),
        "middleware": [
            filesystem_middleware(
                backend, [*READ_TOOLS, "execute"], READ_ONLY_PERMISSIONS
            )
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": [
            "/agent_skills/common",
            "/agent_skills/tester",
            "/agent_skills/tester/mutation-testing",
        ],
    }
