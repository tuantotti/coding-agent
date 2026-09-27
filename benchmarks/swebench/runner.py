"""Sequential, resumable SWE-bench patch generation."""

import hashlib
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

from benchmarks.swebench.api import AgentApiClient, AgentApiError, AgentTimedOut
from benchmarks.swebench.artifacts import ArtifactStore, AttemptResult
from benchmarks.swebench.config import BenchmarkConfig
from benchmarks.swebench.models import AttemptStatus, DatasetSelection, StrictRecord
from benchmarks.swebench.patch import CapturedPatch, PatchError, capture_patch
from benchmarks.swebench.prompt import prompt_template_sha256, render_task
from benchmarks.swebench.workspace import WorkspaceError, WorkspaceManager


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunSummary(StrictRecord):
    """Aggregate outcomes for a completed or safely stopped generation command."""

    total: int
    attempted: int
    skipped: int
    counts: dict[str, int]
    predictions_path: Path

    @property
    def completed(self) -> int:
        """Return the count of patch-producing completed attempts."""
        return self.counts.get(AttemptStatus.COMPLETED.value, 0)


class BenchmarkRunner:
    """Execute selected instances one at a time through the agent API."""

    def __init__(
        self,
        config: BenchmarkConfig,
        selection: DatasetSelection,
        workspace_manager: WorkspaceManager,
        api_client: AgentApiClient,
        artifacts: ArtifactStore,
        *,
        patch_capture: Callable[[Path, int], CapturedPatch] = capture_patch,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Inject every side-effecting boundary for deterministic tests."""
        self.config = config
        self.selection = selection
        self.workspace_manager = workspace_manager
        self.api_client = api_client
        self.artifacts = artifacts
        self.patch_capture = patch_capture
        self.clock = clock

    async def run(self) -> RunSummary:
        """Process the selection sequentially and rebuild predictions incrementally."""
        attempted = 0
        skipped = 0
        stop_after_attempt = False
        instance_ids = tuple(item.instance_id for item in self.selection.instances)
        for instance in self.selection.instances:
            if not self.artifacts.should_run(
                instance.instance_id, self.config.retry_failures
            ):
                skipped += 1
                continue
            attempted += 1
            number, attempt_dir = self.artifacts.next_attempt(instance.instance_id)
            task = render_task(instance.problem_statement)
            self.artifacts.write_request(
                attempt_dir,
                {
                    **instance.model_dump(),
                    "task_sha256": hashlib.sha256(task.encode()).hexdigest(),
                    "prompt_template_sha256": prompt_template_sha256(),
                },
            )
            started_at = _utc_iso()
            started = self.clock()
            status = AttemptStatus.API_ERROR
            agent_run_id = None
            agent_output = None
            agent_error = None
            runner_error = None
            patch_text = ""
            try:
                workspace = self.workspace_manager.prepare(instance, attempt_dir)
                try:
                    api_run = await self.api_client.run_to_terminal(
                        task,
                        workspace,
                        self.config.instance_timeout_seconds,
                        lambda record: self.artifacts.append_event(
                            attempt_dir, record
                        ),
                    )
                except (AgentTimedOut, AgentApiError) as exc:
                    if exc.run_id:
                        try:
                            recovery = (
                                self.api_client.observe_until_terminal
                                if isinstance(exc, AgentTimedOut)
                                else self.api_client.continue_to_terminal
                            )
                            api_run = await recovery(
                                exc.run_id,
                                self.config.instance_timeout_seconds,
                                lambda record: self.artifacts.append_event(
                                    attempt_dir, record
                                ),
                            )
                        except (AgentTimedOut, AgentApiError) as recovery_error:
                            status = (
                                AttemptStatus.TIMED_OUT
                                if isinstance(exc, AgentTimedOut)
                                else AttemptStatus.API_ERROR
                            )
                            agent_run_id = exc.run_id
                            runner_error = str(recovery_error)
                            stop_after_attempt = True
                            api_run = None
                    else:
                        status = (
                            AttemptStatus.TIMED_OUT
                            if isinstance(exc, AgentTimedOut)
                            else AttemptStatus.API_ERROR
                        )
                        runner_error = str(exc)
                        stop_after_attempt = exc.occupancy_unknown
                        api_run = None
                if api_run is None:
                    raise _AttemptFinished
                agent_run_id = api_run.run_id
                agent_output = api_run.output
                agent_error = api_run.error
                captured = self.patch_capture(workspace, self.config.max_patch_bytes)
                patch_text = captured.text
                status = (
                    AttemptStatus.AGENT_FAILED
                    if api_run.status == "failed"
                    else AttemptStatus.COMPLETED
                )
            except _AttemptFinished:
                pass
            except WorkspaceError as exc:
                status = AttemptStatus.CHECKOUT_ERROR
                runner_error = str(exc)
            except PatchError as exc:
                status = AttemptStatus.PATCH_ERROR
                runner_error = str(exc)

            raw = patch_text.encode("utf-8")
            result = AttemptResult(
                instance_id=instance.instance_id,
                attempt_number=number,
                status=status,
                agent_run_id=agent_run_id,
                started_at=started_at,
                ended_at=_utc_iso(),
                elapsed_seconds=max(0, self.clock() - started),
                agent_output=agent_output,
                agent_error=agent_error,
                patch_sha256=hashlib.sha256(raw).hexdigest(),
                patch_size_bytes=len(raw),
                runner_error=runner_error,
            )
            self.artifacts.finish_attempt(attempt_dir, result, patch_text)
            self.artifacts.write_predictions(instance_ids, self.config.model_label)
            if stop_after_attempt:
                break

        predictions = self.artifacts.write_predictions(
            instance_ids, self.config.model_label
        )
        counts: Counter[str] = Counter()
        for instance_id in instance_ids:
            latest = self.artifacts.latest_result(instance_id)
            if latest:
                counts[latest[0].status.value] += 1
        return RunSummary(
            total=len(instance_ids),
            attempted=attempted,
            skipped=skipped,
            counts=dict(counts),
            predictions_path=predictions,
        )


class _AttemptFinished(Exception):
    """Internal control flow after a typed attempt result is already populated."""
