"""Shared Deep Agents role configuration."""

from typing import Any

from deepagents import FilesystemMiddleware, FilesystemPermission
from deepagents.backends.protocol import BackendProtocol


READ_ONLY_PERMISSIONS = [
    FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="deny"),
]

WRITE_WITH_APPROVAL_PERMISSIONS = [
    FilesystemPermission(operations=["read"], paths=["/**"], mode="allow"),
    FilesystemPermission(
        operations=["write"], paths=["/agent_skills/**"], mode="deny"
    ),
    FilesystemPermission(operations=["write"], paths=["/**"], mode="interrupt"),
]

READ_TOOLS = ["ls", "read_file", "glob", "grep"]


def filesystem_middleware(
    backend: BackendProtocol, tools: list[str], permissions: list[FilesystemPermission]
) -> FilesystemMiddleware[Any, Any, Any]:
    """Build a role-specific filesystem middleware allowlist."""
    return FilesystemMiddleware(
        backend=backend,
        tools=tools,  # type: ignore[arg-type]
        _permissions=permissions,
    )
