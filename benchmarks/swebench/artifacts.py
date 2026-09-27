"""Durable and resumable SWE-bench run artifacts."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import Field

from benchmarks.swebench.models import AttemptStatus, StrictRecord


class ArtifactError(RuntimeError):
    """Stored benchmark state is missing, corrupt, or incompatible."""


class RunManifest(StrictRecord):
    """Reproducibility identity for a generation run."""

    schema_version: int = 1
    runner_version: str = "1"
    run_id: str
    dataset_name: str
    split: str
    requested_revision: str | None
    resolved_revision: str
    instance_ids: tuple[str, ...]
    model_label: str
    api_url: str
    agent_git_commit: str
    agent_git_dirty: bool
    prompt_template_sha256: str
    instance_timeout_seconds: float
    poll_interval_seconds: float
    max_patch_bytes: int
    agent_settings: dict[str, str | int | bool | None] = Field(default_factory=dict)
    python_version: str
    platform: str
    started_at: str
    completed_at: str | None = None


class AttemptResult(StrictRecord):
    """Terminal outcome and integrity metadata for one attempt."""

    instance_id: str
    attempt_number: int = Field(gt=0)
    status: AttemptStatus
    agent_run_id: str | None = None
    started_at: str
    ended_at: str
    elapsed_seconds: float = Field(ge=0)
    agent_output: str | None = None
    agent_error: str | None = None
    patch_sha256: str
    patch_size_bytes: int = Field(ge=0)
    runner_error: str | None = None


class Prediction(StrictRecord):
    """Official SWE-bench prediction row."""

    instance_id: str
    model_name_or_path: str
    model_patch: str


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _atomic_model(path: Path, value: StrictRecord) -> None:
    _atomic_text(path, value.model_dump_json(indent=2) + "\n")


class ArtifactStore:
    """Own benchmark manifests, attempts, events, and predictions."""

    def __init__(self, root: Path) -> None:
        """Use one run-specific artifact root."""
        self.root = root

    def initialize(self, manifest: RunManifest) -> None:
        """Create the manifest or reject an incompatible resume."""
        path = self.root / "manifest.json"
        if path.exists():
            try:
                existing = RunManifest.model_validate_json(path.read_text())
            except Exception as exc:
                raise ArtifactError("Stored manifest is invalid.") from exc
            temporal = {"started_at", "completed_at"}
            left = existing.model_dump(exclude=temporal)
            right = manifest.model_dump(exclude=temporal)
            if left != right:
                raise ArtifactError("Stored manifest does not match this run.")
            return
        _atomic_model(path, manifest)

    def finalize(self, completed_at: str) -> None:
        """Record successful command completion without changing run identity."""
        path = self.root / "manifest.json"
        try:
            manifest = RunManifest.model_validate_json(path.read_text())
        except Exception as exc:
            raise ArtifactError("Stored manifest is invalid.") from exc
        _atomic_model(path, manifest.model_copy(update={"completed_at": completed_at}))

    def next_attempt(self, instance_id: str) -> tuple[int, Path]:
        """Allocate the next immutable attempt directory."""
        instance_root = self.root / "instances" / instance_id
        instance_root.mkdir(parents=True, exist_ok=True)
        numbers = []
        for path in instance_root.glob("attempt-*"):
            try:
                numbers.append(int(path.name.removeprefix("attempt-")))
            except ValueError:
                continue
        number = max(numbers, default=0) + 1
        attempt = instance_root / f"attempt-{number:03d}"
        attempt.mkdir()
        return number, attempt

    def write_request(self, attempt_dir: Path, value: dict[str, Any]) -> None:
        """Persist the exact projected input and task checksum."""
        _atomic_text(
            attempt_dir / "request.json",
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        )

    def append_event(self, attempt_dir: Path, record: dict[str, Any]) -> None:
        """Append one observed API event durably."""
        target = (
            attempt_dir / "approvals.jsonl"
            if record.get("kind") == "approval"
            else attempt_dir / "events.jsonl"
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def finish_attempt(
        self, attempt_dir: Path, result: AttemptResult, patch_text: str
    ) -> None:
        """Atomically publish patch content before its terminal result."""
        raw = patch_text.encode("utf-8")
        if hashlib.sha256(raw).hexdigest() != result.patch_sha256:
            raise ArtifactError("Patch checksum does not match result metadata.")
        if len(raw) != result.patch_size_bytes:
            raise ArtifactError("Patch size does not match result metadata.")
        _atomic_text(attempt_dir / "patch.diff", patch_text)
        _atomic_model(attempt_dir / "result.json", result)

    def latest_result(
        self, instance_id: str
    ) -> tuple[AttemptResult, str] | None:
        """Return the newest valid terminal result and verified patch."""
        instance_root = self.root / "instances" / instance_id
        if not instance_root.exists():
            return None
        attempts = []
        for path in instance_root.glob("attempt-*"):
            try:
                attempts.append((int(path.name.removeprefix("attempt-")), path))
            except ValueError:
                continue
        for attempt_number, attempt in sorted(attempts, reverse=True):
            result_path = attempt / "result.json"
            patch_path = attempt / "patch.diff"
            if not result_path.exists() or not patch_path.exists():
                continue
            try:
                result = AttemptResult.model_validate_json(result_path.read_text())
                patch = patch_path.read_text(encoding="utf-8")
            except Exception as exc:
                raise ArtifactError(f"Invalid attempt artifact: {attempt}") from exc
            if (
                result.instance_id != instance_id
                or result.attempt_number != attempt_number
            ):
                raise ArtifactError(f"Attempt identity mismatch: {attempt}")
            raw = patch.encode("utf-8")
            if hashlib.sha256(raw).hexdigest() != result.patch_sha256:
                raise ArtifactError(f"Patch checksum mismatch: {attempt}")
            if len(raw) != result.patch_size_bytes:
                raise ArtifactError(f"Patch size mismatch: {attempt}")
            return result, patch
        return None

    def should_run(self, instance_id: str, retry_failures: bool) -> bool:
        """Apply resume policy to one selected instance."""
        latest = self.latest_result(instance_id)
        if latest is None:
            return True
        return retry_failures and latest[0].status != AttemptStatus.COMPLETED

    def write_predictions(
        self, instance_ids: tuple[str, ...], model_label: str
    ) -> Path:
        """Rebuild official JSONL in stable selected-instance order."""
        lines = []
        for instance_id in instance_ids:
            latest = self.latest_result(instance_id)
            patch = ""
            if latest and latest[0].status == AttemptStatus.COMPLETED:
                patch = latest[1]
            prediction = Prediction(
                instance_id=instance_id,
                model_name_or_path=model_label,
                model_patch=patch,
            )
            lines.append(prediction.model_dump_json())
        path = self.root / "predictions.jsonl"
        _atomic_text(path, "\n".join(lines) + "\n")
        return path
