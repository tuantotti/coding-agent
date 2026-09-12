"""Top-level factory for the coordinated Deep Agents coding team."""

from dataclasses import dataclass
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, LocalShellBackend
from langchain_core.language_models import BaseChatModel
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.state import CompiledStateGraph

from agents.config import READ_ONLY_PERMISSIONS, READ_TOOLS, filesystem_middleware
from agents.information_retriever import create_information_retriever_subagent
from agents.programmer import create_programmer_subagent
from agents.reviewer import create_reviewer_subagent
from agents.tester import create_tester_subagent
from prompts import load_prompt

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
        """Return and validate the workspace root used by all file operations."""
        root = Path(self.workspace_root or Path.cwd()).resolve()
        if not root.is_dir():
            raise ValueError(f"workspace_root must be an existing directory: {root}")
        if self.max_remediation_cycles < 0:
            raise ValueError("max_remediation_cycles must be zero or greater")
        if self.shell_timeout_seconds <= 0:
            raise ValueError("shell_timeout_seconds must be positive")
        return root


def _create_backend(settings: AgentSettings, workspace_root: Path) -> CompositeBackend:
    """Mount packaged skills read-only alongside the approved local workspace."""
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
            "/": FilesystemBackend(root_dir=workspace_root),
        },
    )


def create_coding_agent(settings: AgentSettings | None = None) -> CompiledStateGraph:
    """Build the compiled coordinator graph.

    Invoke the graph with a stable LangGraph ``thread_id``. Writes, deletes, and
    shell commands pause as interrupts and must be resumed by the host application.
    """
    settings = settings or AgentSettings()
    workspace_root = settings.resolved_workspace_root()
    backend = _create_backend(settings, workspace_root)
    subagents = [
        create_programmer_subagent(settings.model, backend),
        create_reviewer_subagent(settings.model, backend),
        create_tester_subagent(settings.model, backend),
        create_information_retriever_subagent(settings.model, backend),
    ]
    return create_deep_agent(
        model=settings.model,
        system_prompt=load_prompt(
            "coordinator",
            workspace_root=workspace_root,
            max_remediation_cycles=settings.max_remediation_cycles,
        ),
        backend=backend,
        middleware=[filesystem_middleware(backend, READ_TOOLS, READ_ONLY_PERMISSIONS)],
        subagents=subagents,
        permissions=READ_ONLY_PERMISSIONS,
        interrupt_on=_APPROVAL_TOOLS,
        checkpointer=settings.checkpointer or InMemorySaver(),
        name="coding_coordinator",
    )
