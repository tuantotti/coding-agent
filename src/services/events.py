"""Bounded, replayable run events independent of HTTP subscribers."""

import asyncio
from collections import deque
from collections.abc import AsyncIterator
from typing import Literal

from pydantic import BaseModel, Field, JsonValue

from models.runs import utc_now

EventKind = Literal[
    "status",
    "text_delta",
    "agent_activity",
    "approval_required",
    "completed",
    "failed",
]


class InvalidCursor(ValueError):
    """The requested cursor is malformed or ahead of this run."""


class ReplayExpired(Exception):
    """Requested events have already left the bounded replay buffer."""


class RunEvent(BaseModel):
    """Public event envelope with a per-run sequence number."""

    event_id: int
    run_id: str
    timestamp: str = Field(default_factory=lambda: utc_now().isoformat())
    event: EventKind
    data: dict[str, JsonValue]


class EventLog:
    """Fan out events without blocking producers on slow readers."""

    def __init__(self, run_id: str, capacity: int = 1000) -> None:
        """Create an independent replay buffer for one run."""
        self.run_id = run_id
        self._events: deque[RunEvent] = deque(maxlen=capacity)
        self._condition = asyncio.Condition()
        self._last_id = 0
        self._finished = False

    async def publish(self, kind: EventKind, data: dict) -> None:
        """Append and notify subscribers atomically."""
        async with self._condition:
            self._last_id += 1
            self._events.append(
                RunEvent(
                    event_id=self._last_id, run_id=self.run_id, event=kind, data=data
                )
            )
            self._finished = kind in {"completed", "failed"}
            self._condition.notify_all()

    def validate_cursor(self, cursor: int) -> None:
        """Validate replay availability before sending response headers."""
        if cursor < 0 or cursor > self._last_id:
            raise InvalidCursor("Event cursor is outside this run's range.")
        if self._events and cursor < self._events[0].event_id - 1:
            raise ReplayExpired("Event replay expired; poll the run for its result.")

    async def subscribe(
        self, cursor: int = 0, heartbeat_seconds: float = 15
    ) -> AsyncIterator[RunEvent | None]:
        """Replay then follow; yield None when a heartbeat is due."""
        while True:
            heartbeat = False
            async with self._condition:
                self.validate_cursor(cursor)
                batch = [item for item in self._events if item.event_id > cursor]
                if not batch:
                    if self._finished:
                        return
                    try:
                        await asyncio.wait_for(
                            self._condition.wait(), timeout=heartbeat_seconds
                        )
                    except TimeoutError:
                        heartbeat = True
            if heartbeat:
                yield None
            for item in batch:
                cursor = item.event_id
                yield item
