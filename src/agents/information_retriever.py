"""Information-retrieval subagent specification."""

from deepagents import SubAgent
from deepagents.backends.protocol import BackendProtocol
from langchain_core.language_models import BaseChatModel

from src.agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from src.prompts import load_prompt
from src.tools.web_search import create_tavily_search_tool


def create_information_retriever_subagent(
    model: str | BaseChatModel, backend: BackendProtocol
) -> SubAgent:
    """Return the read-only researcher with workspace and Tavily access."""
    return {
        "name": "information_retriever",
        "description": "Researches repository context and web sources with citations.",
        "model": model,
        "system_prompt": load_prompt("information_retriever"),
        "tools": [create_tavily_search_tool()],
        "middleware": [
            filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)
        ],
        "permissions": READ_ONLY_PERMISSIONS,
        "skills": ["/agent_skills/common", "/agent_skills/retriever"],
    }
