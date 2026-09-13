"""Synchronous HTTP and SSE transport without presentation concerns."""

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import httpx


class TerminalError(Exception):
    """Base class for concise, user-facing client failures."""


class ProtocolError(TerminalError):
    """The server response did not satisfy the API or SSE contract."""


class NetworkError(TerminalError):
    """The API could not be reached."""


class ReplayExpired(TerminalError):
    """SSE history was lost and the run was polled exactly once."""

    def __init__(self, run: dict[str, Any]) -> None:
        """Retain the single recovery poll for terminal presentation."""
        super().__init__("Event history was lost.")
        self.run = run


@dataclass(frozen=True)
class SSEEvent:
    """A validated server-sent event used by the terminal application."""

    id: int | None
    event: str
    data: dict[str, Any]


class TerminalClient:
    """Submit, observe, poll, and resume runs on one API server."""

    def __init__(
        self,
        api_url: str,
        *,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Create a client with an unlimited streaming read timeout."""
        timeout = httpx.Timeout(10.0, read=None)
        self._client = httpx.Client(
            base_url=api_url.rstrip("/") + "/",
            timeout=timeout,
            transport=transport,
        )
        self._sleep = sleep

    def close(self) -> None:
        """Close the owned HTTP connection pool."""
        self._client.close()

    def __enter__(self) -> "TerminalClient":
        """Return this client for one explicitly scoped session."""
        return self

    def __exit__(self, *exc_info: object) -> None:
        """Close the client when its session scope ends."""
        self.close()

    def start_run(self, task: str, source_folder: str) -> dict[str, Any]:
        """Submit an opaque server-side path and task."""
        return self._json_request(
            "POST",
            "v1/runs",
            json={"task": task, "source_folder": source_folder},
        )

    def resume(
        self, run_id: str, decisions: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any]:
        """Submit one complete interrupt-to-decisions mapping."""
        return self._json_request(
            "POST", f"v1/runs/{run_id}/resume", json={"decisions": decisions}
        )

    def get_run(self, run_id: str) -> dict[str, Any]:
        """Poll one public run snapshot."""
        return self._json_request("GET", f"v1/runs/{run_id}")

    def events(self, run_id: str) -> Iterator[SSEEvent]:
        """Follow events, replaying from the last received ID after drops."""
        last_id: int | None = None
        retries = 0
        delays = (0.5, 1.0, 2.0)
        while True:
            headers = {"Accept": "text/event-stream"}
            if last_id is not None:
                headers["Last-Event-ID"] = str(last_id)
            terminal = False
            try:
                with self._client.stream(
                    "GET", f"v1/runs/{run_id}/events", headers=headers
                ) as response:
                    if not response.is_success:
                        response.read()
                    if response.status_code == 409 and self._is_replay_expired(
                        response
                    ):
                        raise ReplayExpired(self._replay_snapshot(run_id))
                    self._raise_for_status(response)
                    for event in self._parse_sse(response.iter_lines()):
                        if event.event == "replay_expired":
                            raise ReplayExpired(self._replay_snapshot(run_id))
                        if event.id is not None:
                            if last_id is not None and event.id <= last_id:
                                continue
                            last_id = event.id
                        yield event
                        if event.event in {"completed", "failed"}:
                            terminal = True
                            return
            except ReplayExpired:
                raise
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                if retries >= len(delays):
                    raise NetworkError("Connection to the API was lost.") from exc
            if terminal:
                return
            if retries >= len(delays):
                raise ProtocolError("SSE connection closed before the run finished.")
            self._sleep(delays[retries])
            retries += 1

    def _json_request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = self._client.request(method, path, **kwargs)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise NetworkError("Could not connect to the coding-agent API.") from exc
        self._raise_for_status(response)
        try:
            value = response.json()
        except ValueError as exc:
            raise ProtocolError("Server returned malformed JSON.") from exc
        if not isinstance(value, dict):
            raise ProtocolError("Server returned a JSON value that is not an object.")
        return value

    def _replay_snapshot(self, run_id: str) -> dict[str, Any]:
        run = self.get_run(run_id)
        status = run.get("status")
        valid = (
            run.get("run_id") == run_id
            and isinstance(status, str)
            and status
            in {"queued", "running", "awaiting_approval", "completed", "failed"}
        )
        if status == "completed":
            valid = valid and isinstance(run.get("output"), str)
        elif status == "failed":
            valid = valid and isinstance(run.get("error"), str)
        if not valid:
            raise ProtocolError("Server returned a malformed run snapshot.")
        return run

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        detail = None
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"]
            elif isinstance(body, dict) and isinstance(body.get("detail"), list):
                detail = TerminalClient._validation_detail(body["detail"])
        except ValueError:
            pass
        raise ProtocolError(detail or f"Server returned HTTP {response.status_code}.")

    @staticmethod
    def _validation_detail(items: list[Any]) -> str | None:
        messages = []
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("msg"), str):
                continue
            location = item.get("loc")
            if not isinstance(location, list) or not all(
                isinstance(part, (str, int)) and not isinstance(part, bool)
                for part in location
            ):
                continue
            prefix = ".".join(str(part) for part in location)
            messages.append(f"{prefix}: {item['msg']}" if prefix else item["msg"])
        return "; ".join(messages) or None

    @staticmethod
    def _is_replay_expired(response: httpx.Response) -> bool:
        try:
            body = response.json()
        except ValueError:
            return False
        detail = body.get("detail", "") if isinstance(body, dict) else ""
        return isinstance(detail, str) and "replay" in detail.lower()

    @staticmethod
    def _parse_sse(lines: Iterator[str]) -> Iterator[SSEEvent]:
        fields: dict[str, list[str]] = {}
        for line in lines:
            if line == "":
                if fields:
                    yield TerminalClient._build_event(fields)
                    fields = {}
                continue
            if line.startswith(":"):
                continue
            name, separator, value = line.partition(":")
            if not separator:
                raise ProtocolError("Malformed SSE field.")
            fields.setdefault(name, []).append(value.removeprefix(" "))
        if fields:
            yield TerminalClient._build_event(fields)

    @staticmethod
    def _build_event(fields: dict[str, list[str]]) -> SSEEvent:
        try:
            kind = fields["event"][-1]
            data = json.loads("\n".join(fields["data"]))
            event_id = int(fields["id"][-1]) if "id" in fields else None
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise ProtocolError("Malformed JSON or SSE event.") from exc
        if (
            not kind
            or not isinstance(data, dict)
            or (event_id is None and kind != "replay_expired")
            or (event_id is not None and event_id < 0)
        ):
            raise ProtocolError("Malformed JSON or SSE event.")
        TerminalClient._validate_event(kind, data)
        return SSEEvent(event_id, kind, data)

    @staticmethod
    def _validate_event(kind: str, data: dict[str, Any]) -> None:
        allowed = {
            "status",
            "agent_activity",
            "text_delta",
            "approval_required",
            "completed",
            "failed",
            "replay_expired",
        }
        if kind not in allowed:
            raise ProtocolError(f"Unknown SSE event type: {kind}.")
        valid = False
        if kind == "status":
            status = data.get("status")
            valid = isinstance(status, str) and status in {"queued", "running"}
        elif kind == "agent_activity":
            valid = TerminalClient._strings(data, "agent", "status")
        elif kind == "text_delta":
            valid = TerminalClient._strings(data, "text", "agent")
        elif kind == "completed":
            valid = data.get("status") == "completed" and isinstance(
                data.get("output"), str
            )
        elif kind == "failed":
            valid = data.get("status") == "failed" and isinstance(
                data.get("error"), str
            )
        elif kind == "approval_required":
            valid = data.get(
                "status"
            ) == "awaiting_approval" and TerminalClient._valid_approvals(
                data.get("approvals")
            )
        elif kind == "replay_expired":
            valid = isinstance(data.get("error"), str)
        if not valid:
            raise ProtocolError(f"Malformed {kind} event data.")

    @staticmethod
    def _strings(data: dict[str, Any], *names: str) -> bool:
        return all(isinstance(data.get(name), str) for name in names)

    @staticmethod
    def _valid_approvals(value: Any) -> bool:
        if not isinstance(value, list) or not value:
            return False
        interrupt_ids = set()
        for approval in value:
            if not isinstance(approval, dict):
                return False
            interrupt_id = approval.get("interrupt_id")
            actions = approval.get("action_requests")
            review_configs = approval.get("review_configs")
            if (
                not isinstance(interrupt_id, str)
                or not interrupt_id
                or interrupt_id in interrupt_ids
                or not isinstance(actions, list)
                or not actions
                or not isinstance(review_configs, list)
            ):
                return False
            interrupt_ids.add(interrupt_id)
            if not all(TerminalClient._valid_action(action) for action in actions):
                return False
            if not all(
                TerminalClient._valid_review_config(config) for config in review_configs
            ):
                return False
        return True

    @staticmethod
    def _valid_review_config(config: Any) -> bool:
        if not isinstance(config, dict):
            return False
        action_name = config.get("action_name")
        allowed = config.get("allowed_decisions")
        args_schema = config.get("args_schema")
        if (
            not isinstance(action_name, str)
            or not action_name
            or not isinstance(allowed, list)
            or not all(
                isinstance(decision, str) and decision in {"approve", "edit", "reject"}
                for decision in allowed
            )
            or (args_schema is not None and not isinstance(args_schema, dict))
        ):
            return False
        try:
            json.dumps(args_schema, allow_nan=False)
        except (TypeError, ValueError):
            return False
        return True

    @staticmethod
    def _valid_action(action: Any) -> bool:
        if not isinstance(action, dict):
            return False
        name = action.get("name")
        description = action.get("description")
        args = action.get("args")
        if (
            not isinstance(name, str)
            or not name
            or (description is not None and not isinstance(description, str))
            or not isinstance(args, dict)
        ):
            return False
        try:
            json.dumps(args, allow_nan=False)
        except (TypeError, ValueError):
            return False
        return True
