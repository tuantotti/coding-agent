"""Asynchronous black-box client for coding-agent benchmark runs."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import httpx
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError


class AgentApiError(RuntimeError):
    """The coding-agent API did not complete a valid protocol exchange."""

    def __init__(
        self,
        message: str,
        *,
        run_id: str | None = None,
        occupancy_unknown: bool = False,
    ) -> None:
        """Retain recovery data when the server may still own an active run."""
        super().__init__(message)
        self.run_id = run_id
        self.occupancy_unknown = occupancy_unknown


class AgentTimedOut(AgentApiError):
    """A run exceeded its generation deadline."""

    def __init__(self, run_id: str | None) -> None:
        """Retain the last known API run identifier for recovery."""
        super().__init__(
            "The coding-agent run exceeded its deadline.",
            run_id=run_id,
            occupancy_unknown=True,
        )


class ApiRecord(BaseModel):
    """Strict API response base."""

    model_config = ConfigDict(extra="forbid")


class ApiAction(ApiRecord):
    """One proposed agent tool action."""

    name: str
    args: dict[str, JsonValue]
    description: str | None = None


class ApiApproval(ApiRecord):
    """An interrupt containing ordered action requests."""

    interrupt_id: str
    action_requests: list[ApiAction]
    review_configs: list["ApiReviewConfig"]


class ApiReviewConfig(ApiRecord):
    """Allowed decisions for one action name."""

    action_name: str
    allowed_decisions: list[Literal["approve", "edit", "reject", "respond"]]
    args_schema: dict[str, JsonValue] | None = None


class ApiRun(ApiRecord):
    """Validated public run snapshot."""

    run_id: str
    source_folder: str
    status: Literal["queued", "running", "awaiting_approval", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    output: str | None = None
    approvals: list[ApiApproval] = Field(default_factory=list)
    error: str | None = None


class BenchmarkServerSettings(ApiRecord):
    """Effective non-secret server settings that define benchmark integrity."""

    model: str = Field(min_length=1)
    max_remediation_cycles: int = Field(ge=0)
    shell_timeout_seconds: int = Field(gt=0)
    web_search_enabled: bool


EventSink = Callable[[dict[str, Any]], None]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentApiClient:
    """Start, observe, approve, and finish one coding-agent API run."""

    _RETRY_DELAYS = (0.5, 1.0, 2.0)

    def __init__(
        self,
        api_url: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        """Create a scoped async HTTP client."""
        self._client = httpx.AsyncClient(
            base_url=api_url.rstrip("/") + "/",
            transport=transport,
            timeout=httpx.Timeout(30.0),
        )
        self._sleep = sleep
        self._poll_interval_seconds = poll_interval_seconds

    async def __aenter__(self) -> "AgentApiClient":
        """Return this scoped client."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Close connections when leaving the scope."""
        await self.close()

    async def close(self) -> None:
        """Close the owned connection pool."""
        await self._client.aclose()

    async def require_benchmark_safe(self) -> BenchmarkServerSettings:
        """Return effective settings only when external web lookup is disabled."""
        logger.info("Checking benchmark API settings")
        last_error: Exception | None = None
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                response = await self._client.get("v1/benchmark-config")
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            else:
                if response.is_success:
                    try:
                        effective = BenchmarkServerSettings.model_validate(
                            response.json()
                        )
                    except (ValueError, ValidationError) as exc:
                        raise AgentApiError(
                            "API returned malformed benchmark settings."
                        ) from exc
                    if effective.web_search_enabled:
                        raise AgentApiError(
                            "Benchmark refused because server web search is enabled."
                        )
                    logger.info(
                        "Benchmark API preflight passed model={}", effective.model
                    )
                    return effective
                if response.status_code < 500:
                    raise AgentApiError(
                        "Coding-agent API does not expose safe benchmark settings "
                        f"(HTTP {response.status_code})."
                    )
                last_error = AgentApiError(
                    f"Coding-agent API returned HTTP {response.status_code}."
                )
            if attempt < len(self._RETRY_DELAYS):
                logger.warning(
                    "API preflight retry={} delay={}s reason={}",
                    attempt + 1,
                    self._RETRY_DELAYS[attempt],
                    last_error,
                )
                await self._sleep(self._RETRY_DELAYS[attempt])
        raise AgentApiError(
            "Coding-agent benchmark preflight retries were exhausted."
        ) from last_error

    async def start(self, task: str, source_folder: Path) -> ApiRun:
        """Create a run, retrying a transient global-run conflict."""
        logger.info("Starting agent run workspace={}", source_folder)
        return await self._request_run(
            "POST",
            "v1/runs",
            json={"task": task, "source_folder": str(source_folder.resolve())},
            retry_conflict=True,
        )

    async def get(self, run_id: str) -> ApiRun:
        """Fetch one run snapshot."""
        return await self._request_run("GET", f"v1/runs/{run_id}")

    async def approve(self, run: ApiRun) -> ApiRun:
        """Approve every action in server-provided order."""
        self._validate_approvals(run)
        logger.info(
            "Automatically approving agent_run={} actions={}",
            run.run_id,
            sum(len(item.action_requests) for item in run.approvals),
        )
        decisions = {
            approval.interrupt_id: [
                {"type": "approve"} for _ in approval.action_requests
            ]
            for approval in run.approvals
        }
        return await self._request_run(
            "POST",
            f"v1/runs/{run.run_id}/resume",
            json={"decisions": decisions},
        )

    async def run_to_terminal(
        self,
        task: str,
        source_folder: Path,
        timeout_seconds: float,
        event_sink: EventSink,
    ) -> ApiRun:
        """Run one task through approval pauses to a terminal snapshot."""
        run_id: str | None = None
        try:
            async with asyncio.timeout(timeout_seconds):
                run = await self.start(task, source_folder)
                run_id = run.run_id
                return await self._drive(run, event_sink)
        except TimeoutError as exc:
            logger.warning("Agent run={} timed out after {}s", run_id, timeout_seconds)
            raise AgentTimedOut(run_id) from exc
        except AgentApiError as exc:
            if run_id and not exc.run_id:
                raise AgentApiError(
                    str(exc), run_id=run_id, occupancy_unknown=True
                ) from exc
            raise

    async def continue_to_terminal(
        self,
        run_id: str,
        timeout_seconds: float,
        event_sink: EventSink,
    ) -> ApiRun:
        """Recover a known run after a timeout or transient polling failure."""
        try:
            async with asyncio.timeout(timeout_seconds):
                return await self._drive(await self.get(run_id), event_sink)
        except TimeoutError as exc:
            raise AgentTimedOut(run_id) from exc
        except AgentApiError as exc:
            raise AgentApiError(
                str(exc), run_id=run_id, occupancy_unknown=True
            ) from exc

    async def observe_until_terminal(
        self,
        run_id: str,
        timeout_seconds: float,
        event_sink: EventSink,
    ) -> ApiRun:
        """Observe a timed-out run without authorizing any additional actions."""
        try:
            async with asyncio.timeout(timeout_seconds):
                while True:
                    run = await self.get(run_id)
                    event_sink(
                        {
                            "kind": "snapshot",
                            "observed_at": _utc_iso(),
                            "run": run.model_dump(mode="json"),
                        }
                    )
                    if run.status in {"completed", "failed"}:
                        return run
                    if run.status == "awaiting_approval":
                        raise AgentTimedOut(run_id)
                    await self._sleep(self._poll_interval_seconds)
        except TimeoutError as exc:
            raise AgentTimedOut(run_id) from exc
        except AgentApiError as exc:
            if isinstance(exc, AgentTimedOut):
                raise
            raise AgentApiError(
                str(exc), run_id=run_id, occupancy_unknown=True
            ) from exc

    async def _drive(self, run: ApiRun, event_sink: EventSink) -> ApiRun:
        while True:
            event_sink(
                {
                    "kind": "snapshot",
                    "observed_at": _utc_iso(),
                    "run": run.model_dump(mode="json"),
                }
            )
            if run.status in {"completed", "failed"}:
                return run
            if run.status == "awaiting_approval":
                self._validate_approvals(run)
                event_sink(
                    {
                        "kind": "approval",
                        "observed_at": _utc_iso(),
                        "approvals": [
                            item.model_dump(mode="json") for item in run.approvals
                        ],
                    }
                )
                run = await self.approve(run)
            else:
                await self._sleep(self._poll_interval_seconds)
                run = await self.get(run.run_id)

    @staticmethod
    def _validate_approvals(run: ApiRun) -> None:
        if run.status != "awaiting_approval" or not run.approvals:
            raise AgentApiError("Run is not awaiting a complete approval set.")
        interrupt_ids = [item.interrupt_id for item in run.approvals]
        if len(interrupt_ids) != len(set(interrupt_ids)):
            raise AgentApiError("Duplicate interrupt IDs are not allowed.")
        for approval in run.approvals:
            if not approval.action_requests:
                raise AgentApiError("Approval contains no actions.")
            configs = {item.action_name: item for item in approval.review_configs}
            # if len(configs) != len(approval.review_configs):
            #     raise AgentApiError("Duplicate review configurations are not allowed.")
            action_names = {item.name for item in approval.action_requests}
            if action_names != set(configs):
                raise AgentApiError(
                    "Approval actions and review configurations differ."
                )
            for action in approval.action_requests:
                if "approve" not in configs[action.name].allowed_decisions:
                    raise AgentApiError(
                        f"Action {action.name!r} does not allow approval."
                    )

    async def _request_run(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        retry_conflict: bool = False,
    ) -> ApiRun:
        last_error: Exception | None = None
        for attempt in range(len(self._RETRY_DELAYS) + 1):
            try:
                response = await self._client.request(method, path, json=json)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
            else:
                retryable = response.status_code >= 500 or (
                    retry_conflict and response.status_code == 409
                )
                if response.is_success:
                    try:
                        return ApiRun.model_validate(response.json())
                    except (ValueError, ValidationError) as exc:
                        raise AgentApiError(
                            "API returned a malformed run.",
                            occupancy_unknown=method == "POST",
                        ) from exc
                if not retryable:
                    raise AgentApiError(
                        f"Coding-agent API returned HTTP {response.status_code}."
                    )
                last_error = AgentApiError(
                    f"Coding-agent API returned HTTP {response.status_code}.",
                    occupancy_unknown=method == "POST",
                )
            if attempt < len(self._RETRY_DELAYS):
                logger.warning(
                    "API request method={} path={} retry={} delay={}s reason={}",
                    method,
                    path,
                    attempt + 1,
                    self._RETRY_DELAYS[attempt],
                    last_error,
                )
                await self._sleep(self._RETRY_DELAYS[attempt])
        raise AgentApiError(
            "Coding-agent API retries were exhausted.",
            occupancy_unknown=method == "POST",
        ) from last_error
