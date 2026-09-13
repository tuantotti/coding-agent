"""Run lifecycle and human approval contracts."""

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue


def resolve_source_folder(value: Path | str) -> Path:
    """Resolve an explicitly supplied, readable absolute source directory."""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError("source_folder must be an absolute path.")
    try:
        path = path.resolve(strict=True)
        if not path.is_dir() or not os.access(path, os.R_OK | os.X_OK):
            raise ValueError("source_folder must be a readable directory.")
    except (OSError, RuntimeError) as exc:
        raise ValueError("source_folder must be an accessible directory.") from exc
    return path


SourceFolder = Annotated[Path, AfterValidator(resolve_source_folder)]


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(timezone.utc)


class Contract(BaseModel):
    """Reject unknown input fields."""

    model_config = ConfigDict(extra="forbid")


class StartRun(Contract):
    """Request a coding task."""

    task: str = Field(min_length=1, max_length=50000)
    source_folder: SourceFolder

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Action(Contract):
    """Tool action awaiting a human decision."""

    name: str = Field(min_length=1)
    args: dict[str, JsonValue]


class ActionRequest(Action):
    """Tool action with human-readable context."""

    description: str | None = None


class ReviewConfig(Contract):
    """Allowed decisions for a requested action."""

    action_name: str
    allowed_decisions: list[str]
    args_schema: dict[str, JsonValue] | None = None


class PendingApproval(Contract):
    """An interrupt and its ordered action requests."""

    interrupt_id: str
    action_requests: list[ActionRequest]
    review_configs: list[ReviewConfig]


class Approve(Contract):
    """Authorize the original action."""

    type: Literal["approve"]


class Edit(Contract):
    """Authorize an edited action."""

    type: Literal["edit"]
    edited_action: Action


class Reject(Contract):
    """Reject an action with optional feedback."""

    type: Literal["reject"]
    message: str | None = None


Decision = Annotated[Approve | Edit | Reject, Field(discriminator="type")]


class ResumeRun(Contract):
    """Decisions keyed by interrupt ID, in action-request order."""

    decisions: dict[str, list[Decision]]


class Run(Contract):
    """Public run state; internal graph state is never returned."""

    run_id: str
    source_folder: Path
    status: Literal["queued", "running", "awaiting_approval", "completed", "failed"] = (
        "queued"
    )
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    output: str | None = None
    approvals: list[PendingApproval] = Field(default_factory=list)
    error: str | None = None
