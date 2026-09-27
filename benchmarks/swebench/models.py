"""Strict data contracts shared by the SWE-bench runner."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class StrictRecord(BaseModel):
    """Reject unknown fields and make benchmark records immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class BenchmarkInstance(StrictRecord):
    """The only dataset fields permitted beyond the loading boundary."""

    instance_id: str
    repo: str
    base_commit: str
    problem_statement: str


class DatasetSelection(StrictRecord):
    """Pinned, ordered benchmark input."""

    dataset_name: str
    split: str
    requested_revision: str | None
    resolved_revision: str
    instances: tuple[BenchmarkInstance, ...]


class AttemptStatus(StrEnum):
    """Terminal outcome for one agent attempt."""

    COMPLETED = "completed"
    AGENT_FAILED = "agent_failed"
    TIMED_OUT = "timed_out"
    API_ERROR = "api_error"
    CHECKOUT_ERROR = "checkout_error"
    PATCH_ERROR = "patch_error"
