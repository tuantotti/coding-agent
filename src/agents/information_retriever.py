"""Information-retrieval subagent specification."""

from pathlib import Path

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from src.prompts import load_prompt
from src.tools.web_search import create_tavily_search_tool


def create_information_retriever_subagent(
    model: str | BaseChatModel,
    backend: BackendProtocol,
    *,
    workspace_root: str | Path = ".",
    web_search_enabled: bool = True,
) -> SubAgent:
    """Return the read-only researcher with optional external web access."""
    tools = [create_tavily_search_tool()] if web_search_enabled else []
    description = (
        "Researches repository context and web sources with citations."
        if web_search_enabled
        else "Researches repository context without external web access."
    )
    return {
        "name": "information_retriever",
        "description": description,
        "model": model,
        "system_prompt": load_prompt(
            "information_retriever", workspace_root=workspace_root
        ),
        "tools": tools,
        "middleware": [
            filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/retriever"],
    }
