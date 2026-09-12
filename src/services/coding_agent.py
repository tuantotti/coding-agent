"""Manage serialized, resumable background runs."""

import asyncio
import logging
from collections.abc import MutableMapping
from typing import Any, Protocol
from uuid import uuid4

from langchain_core.messages import AIMessage
from langgraph.types import Command

from models.runs import PendingApproval, ResumeRun, Run, utc_now

logger = logging.getLogger(__name__)


class AgentGraph(Protocol):
    """Minimal graph interface required by the service."""

    async def ainvoke(self, input: Any, config: dict) -> dict:
        """Invoke or resume the graph asynchronously."""
        ...


class RunNotFound(Exception):
    """The requested run does not exist."""


class RunConflict(Exception):
    """The workspace or run is not in an acceptable state."""


class InvalidApproval(Exception):
    """Approval decisions do not match pending actions."""


class CodingAgentService:
    """Own graph lifetime, run state, and workspace serialization."""

    def __init__(
        self, graph: AgentGraph, store: MutableMapping[str, Run] | None = None
    ) -> None:
        """Inject a graph and optional in-memory-compatible run store."""
        self._graph = graph
        self._store = store if store is not None else {}
        self._lock = asyncio.Lock()
        self._tasks: set[asyncio.Task] = set()
        self._closed = False

    def get(self, run_id: str) -> Run:
        """Return a detached snapshot of a run."""
        try:
            return self._store[run_id].model_copy(deep=True)
        except KeyError as exc:
            raise RunNotFound("Run not found.") from exc

    async def start(self, task: str) -> Run:
        """Reserve the workspace and schedule a new run."""
        async with self._lock:
            if self._closed or any(
                run.status not in {"completed", "failed"}
                for run in self._store.values()
            ):
                raise RunConflict("Workspace already has an unfinished run.")
            run = Run(run_id=str(uuid4()))
            self._store[run.run_id] = run
            self._schedule(
                run.run_id, {"messages": [{"role": "user", "content": task}]}
            )
            return self.get(run.run_id)

    async def resume(self, run_id: str, request: ResumeRun) -> Run:
        """Validate all pending decisions atomically, then schedule resumption."""
        async with self._lock:
            run = self.get(run_id)
            if self._closed or run.status != "awaiting_approval":
                raise RunConflict("Run is not awaiting approval.")
            expected = {item.interrupt_id for item in run.approvals}
            if set(request.decisions) != expected:
                raise InvalidApproval("Supply exactly the pending interrupt IDs.")
            payload = {}
            for approval in run.approvals:
                decisions = request.decisions[approval.interrupt_id]
                if len(decisions) != len(approval.action_requests):
                    raise InvalidApproval("One decision is required per action.")
                configs = {item.action_name: item for item in approval.review_configs}
                for action, decision in zip(
                    approval.action_requests, decisions, strict=True
                ):
                    config = configs.get(action.name)
                    if config is None or decision.type not in config.allowed_decisions:
                        raise InvalidApproval(
                            "Decision is not allowed for this action."
                        )
                    if (
                        decision.type == "edit"
                        and decision.edited_action.name != action.name
                    ):
                        raise InvalidApproval("Edits must preserve the tool name.")
                payload[approval.interrupt_id] = {
                    "decisions": [
                        decision.model_dump(exclude_none=True) for decision in decisions
                    ]
                }
            run.status = "queued"
            run.approvals = []
            run.updated_at = utc_now()
            self._store[run_id] = run
            self._schedule(run_id, Command(resume=payload))
            return self.get(run_id)

    def _schedule(self, run_id: str, input: Any) -> None:
        task = asyncio.create_task(self._execute(run_id, input))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _execute(self, run_id: str, input: Any) -> None:
        run = self._store[run_id]
        run.status = "running"
        run.updated_at = utc_now()
        try:
            result = await self._graph.ainvoke(
                input, {"configurable": {"thread_id": run_id}, "recursion_limit": 200}
            )
            interrupts = result.get("__interrupt__", ())
            if interrupts:
                run.approvals = [
                    PendingApproval(interrupt_id=item.id, **item.value)
                    for item in interrupts
                ]
                run.status = "awaiting_approval"
            else:
                run.output = next(
                    (
                        message.text
                        for message in reversed(result.get("messages", []))
                        if isinstance(message, AIMessage) and message.text
                    ),
                    "",
                )
                run.status = "completed"
        except asyncio.CancelledError:
            run.status = "failed"
            run.error = "Run stopped during application shutdown."
            raise
        except Exception:
            # Provider exceptions can contain secrets; never include their text.
            logger.error("Coding run %s failed", run_id)
            run.status = "failed"
            run.error = "Agent execution failed."
        finally:
            run.updated_at = utc_now()
            self._store[run_id] = run

    async def close(self) -> None:
        """Stop accepting work and await cancellation of tracked jobs."""
        async with self._lock:
            self._closed = True
            tasks = tuple(self._tasks)
            for task in tasks:
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for run in self._store.values():
            if run.status not in {"completed", "failed"}:
                run.status = "failed"
                run.error = "Run stopped during application shutdown."
                run.updated_at = utc_now()
