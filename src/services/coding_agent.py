"""Manage serialized, resumable background runs."""

import asyncio
from collections.abc import Callable, MutableMapping
from pathlib import Path
from typing import Any
from uuid import uuid4

from jsonschema import ValidationError, validate
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command
from loguru import logger

from src.models.runs import (
    PendingApproval,
    ResumeRun,
    Run,
    resolve_source_folder,
    utc_now,
)
from src.services.events import EventLog
from src.services.graph_stream import AgentGraph, GraphStream
from src.services.tracing import with_tracing_callback
from src.tools.approval import include_argument_schemas


class InvalidSourceFolder(ValueError):
    """The requested source directory cannot be used."""


class RunNotFound(Exception):
    """The requested run does not exist."""


class RunConflict(Exception):
    """The workspace or run is not in an acceptable state."""


class InvalidApproval(Exception):
    """Approval decisions do not match pending actions."""


class CodingAgentService:
    """Own graph lifetime, run state, and workspace serialization."""

    def __init__(
        self,
        graph_factory: Callable[[Path], AgentGraph],
        store: MutableMapping[str, Run] | None = None,
        *,
        callback_factory: Callable[[], BaseCallbackHandler] | None = None,
    ) -> None:
        """Inject a per-workspace graph factory and optional run store."""
        self._graph_factory = graph_factory
        self._callback_factory = callback_factory
        self._graphs: dict[str, AgentGraph] = {}
        self._events: dict[str, EventLog] = {}
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

    def event_log(self, run_id: str) -> EventLog:
        """Return the run's replay buffer, or raise RunNotFound."""
        self.get(run_id)
        return self._events[run_id]

    async def start(self, task: str, source_folder: Path | str) -> Run:
        """Reserve the workspace and schedule a new run."""
        try:
            root = resolve_source_folder(source_folder)
        except ValueError as exc:
            raise InvalidSourceFolder(str(exc)) from exc
        async with self._lock:
            if self._closed or any(
                run.status not in {"completed", "failed"}
                for run in self._store.values()
            ):
                raise RunConflict("Workspace already has an unfinished run.")
            run = Run(run_id=str(uuid4()), source_folder=root)
            self._store[run.run_id] = run
            self._events[run.run_id] = EventLog(run.run_id)
            logger.info(
                "Coding run accepted run_id={} status={}", run.run_id, run.status
            )
            await self._events[run.run_id].publish("status", {"status": run.status})
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
                    if decision.type == "edit" and config.args_schema is not None:
                        try:
                            validate(decision.edited_action.args, config.args_schema)
                        except ValidationError as exc:
                            raise InvalidApproval(
                                "Edited arguments do not match the tool schema."
                            ) from exc
                payload[approval.interrupt_id] = {
                    "decisions": [
                        decision.model_dump(exclude_none=True) for decision in decisions
                    ]
                }
            run.status = "queued"
            run.approvals = []
            run.updated_at = utc_now()
            self._store[run_id] = run
            logger.info("Coding run resumed run_id={} status={}", run_id, run.status)
            await self._events[run_id].publish("status", {"status": run.status})
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
        logger.info(
            "Coding run execution started run_id={} status={}", run_id, run.status
        )
        events = self._events[run_id]
        try:
            await events.publish("status", {"status": run.status})
            if run_id not in self._graphs:
                self._graphs[run_id] = await asyncio.to_thread(
                    self._graph_factory, run.source_folder
                )
            stream = GraphStream()
            config: RunnableConfig = {
                "configurable": {"thread_id": run_id},
                "recursion_limit": 200,
            }
            if self._callback_factory is not None:
                config = with_tracing_callback(config, self._callback_factory(), run_id)
            async for kind, data in stream.events(
                self._graphs[run_id],
                input,
                config,
            ):
                await events.publish(kind, data)
            interrupts = stream.interrupts.values()
            if interrupts:
                run.approvals = [
                    include_argument_schemas(
                        PendingApproval(interrupt_id=item.id, **item.value)
                    )
                    for item in interrupts
                ]
                run.status = "awaiting_approval"
                logger.info(
                    "Coding run approval requested run_id={} status={}",
                    run_id,
                    run.status,
                )
                await events.publish(
                    "approval_required",
                    {
                        "status": run.status,
                        "approvals": [
                            approval.model_dump(mode="json")
                            for approval in run.approvals
                        ],
                    },
                )
            else:
                run.output = stream.output()
                run.status = "completed"
                logger.info(
                    "Coding run completed run_id={} status={}", run_id, run.status
                )
        except asyncio.CancelledError:
            run.status = "failed"
            run.error = "Run stopped during application shutdown."
            logger.info("Coding run cancelled run_id={} status={}", run_id, run.status)
            raise
        except Exception as e:
            # Provider exceptions can contain secrets; never include their text.
            run.status = "failed"
            run.error = "Agent execution failed."
            logger.error(e)
            logger.error("Coding run failed run_id={} status={}", run_id, run.status)
        finally:
            run.updated_at = utc_now()
            self._store[run_id] = run
            if run.status in {"completed", "failed"}:
                self._graphs.pop(run_id, None)
                await events.publish(
                    run.status,
                    {
                        "status": run.status,
                        "output": run.output,
                        "error": run.error,
                    },
                )

    async def close(self) -> None:
        """Stop accepting work and await cancellation of tracked jobs."""
        logger.info("Coding agent shutdown started")
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
                self._graphs.pop(run.run_id, None)
                logger.info(
                    "Coding run cancelled during shutdown run_id={} status={}",
                    run.run_id,
                    run.status,
                )
                await self._events[run.run_id].publish(
                    "failed",
                    {
                        "status": run.status,
                        "error": run.error,
                    },
                )
        logger.info("Coding agent shutdown completed")
