"""Top-level factory for the coordinated Deep Agents coding team."""

from dataclasses import dataclass
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, LocalShellBackend
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from src.agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from src.agents.information_retriever import create_information_retriever_subagent
from src.agents.requirement import create_requirement_subagent
from src.agents.programmer import create_programmer_subagent
from src.agents.reviewer import create_reviewer_subagent
from src.agents.tester import create_tester_subagent
from src.models.llms import create_azure_model
from src.prompts import load_prompt

_SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
_APPROVAL_TOOLS = {
    "write_file": True,
    "edit_file": True,
    "delete": True,
    "execute": True,
}


@dataclass(slots=True)
class AgentSettings:
    """Configuration for a coding-agent graph.

    ``LocalShellBackend`` runs approved commands on the host, not in a container.
    Use this only for a trusted local workspace.
    """

    workspace_root: Path | str | None = None
    model: str | BaseChatModel = "openai:gpt-5.4"
    checkpointer: BaseCheckpointSaver | None = None
    max_remediation_cycles: int = 2
    shell_timeout_seconds: int = 120

    def resolved_workspace_root(self) -> Path:
        """Validate the project context and shell working directory."""
        root = Path(self.workspace_root or Path.cwd()).resolve()
        if not root.is_dir():
            raise ValueError(f"workspace_root must be an existing directory: {root}")
        if self.max_remediation_cycles < 0:
            raise ValueError("max_remediation_cycles must be zero or greater")
        if self.shell_timeout_seconds <= 0:
            raise ValueError("shell_timeout_seconds must be positive")
        return root


def _create_backend(settings: AgentSettings, workspace_root: Path) -> CompositeBackend:
    """Expose host paths alongside the protected virtual skills mount."""
    workspace = LocalShellBackend(
        root_dir=workspace_root,
        timeout=settings.shell_timeout_seconds,
        inherit_env=True,
    )
    packaged_skills = FilesystemBackend(root_dir=_SKILLS_ROOT)
    return CompositeBackend(
        default=workspace,
        routes={
            "/agent_skills/": packaged_skills,
            "/": FilesystemBackend(root_dir=workspace_root, virtual_mode=False),
        },
    )


def create_coding_agent(settings: AgentSettings | None = None) -> CompiledStateGraph:
    """Build the compiled coordinator graph.

    Invoke the graph with a stable LangGraph ``thread_id``. Writes, deletes, and
    shell commands pause as interrupts and must be resumed by the host application.
    """
    agent_settings = settings or AgentSettings()
    workspace_root = agent_settings.resolved_workspace_root()
    backend = _create_backend(agent_settings, workspace_root)
    subagents = [
        create_requirement_subagent(
            create_azure_model(deployment=agent_settings.model), backend
        ),
        create_programmer_subagent(
            create_azure_model(deployment=agent_settings.model), backend
        ),
        create_reviewer_subagent(
            create_azure_model(deployment=agent_settings.model), backend
        ),
        create_tester_subagent(
            create_azure_model(deployment=agent_settings.model), backend
        ),
        create_information_retriever_subagent(
            create_azure_model(deployment=agent_settings.model), backend
        ),
    ]
    return create_deep_agent(
        model=create_azure_model(deployment=agent_settings.model),
        system_prompt=load_prompt(
            "coordinator",
            workspace_root=workspace_root,
            max_remediation_cycles=agent_settings.max_remediation_cycles,
        ),
        backend=backend,
        middleware=[filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)],
        subagents=subagents,
        permissions=READ_ONLY_PERMISSIONS,
        interrupt_on=_APPROVAL_TOOLS,
        checkpointer=agent_settings.checkpointer or InMemorySaver(),
        name="coding_coordinator",
    )
