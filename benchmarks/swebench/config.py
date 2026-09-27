"""Validated runner configuration."""

import re
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator

from benchmarks.swebench.models import StrictRecord

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9_.-]+$")


class BenchmarkConfig(StrictRecord):
    """Immutable command configuration for one benchmark generation run."""

    api_url: str
    output_root: Path
    cache_root: Path
    run_id: str
    model_label: str
    dataset_name: str = "SWE-bench/SWE-bench_Verified"
    split: str = "test"
    dataset_revision: str | None = None
    instance_ids: tuple[str, ...] = ()
    all_instances: bool = False
    instance_timeout_seconds: float = Field(default=3600.0, gt=0)
    poll_interval_seconds: float = Field(default=1.0, gt=0)
    max_patch_bytes: int = Field(default=10_000_000, gt=0)
    retry_failures: bool = False
    acknowledge_auto_approval_risk: bool = False

    @field_validator("api_url")
    @classmethod
    def validate_api_url(cls, value: str) -> str:
        """Accept only credential-free HTTP(S) API base URLs."""
        if value != value.strip() or any(character.isspace() for character in value):
            raise ValueError("api_url must not contain whitespace.")
        try:
            parsed = urlsplit(value)
            parsed_port = parsed.port
        except ValueError as exc:
            raise ValueError("api_url is invalid.") from exc
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("api_url must be an HTTP(S) URL with a host.")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("api_url must not contain credentials.")
        if parsed.query or parsed.fragment:
            raise ValueError("api_url must not contain a query or fragment.")
        if parsed_port is not None and not 1 <= parsed_port <= 65535:
            raise ValueError("api_url contains an invalid port.")
        return value.rstrip("/")

    @model_validator(mode="after")
    def validate_run(self) -> "BenchmarkConfig":
        """Prevent ambiguous, unsafe, or accidentally expensive runs."""
        if self.all_instances == bool(self.instance_ids):
            raise ValueError("Choose exactly one of all_instances or instance_ids.")
        if self.all_instances and not self.dataset_revision:
            raise ValueError("A dataset revision is required for a full run.")
        if self.all_instances and not re.fullmatch(
            r"[0-9a-f]{40}", self.dataset_revision or ""
        ):
            raise ValueError("A full run requires an immutable dataset commit SHA.")
        if not _SAFE_TOKEN.fullmatch(self.run_id):
            raise ValueError(
                "run_id must contain only letters, numbers, '.', '-', '_'."
            )
        if not self.model_label.strip():
            raise ValueError("model_label must not be blank.")
        if not self.acknowledge_auto_approval_risk:
            raise ValueError("Automatic approval risk must be acknowledged.")
        if len(set(self.instance_ids)) != len(self.instance_ids):
            raise ValueError("instance_ids must not contain duplicates.")
        return self
