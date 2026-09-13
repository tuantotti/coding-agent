"""Run submission, polling, and approval routes."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from src.models.runs import ResumeRun, Run, StartRun
from src.services.coding_agent import CodingAgentService
from src.services.events import InvalidCursor, ReplayExpired

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def get_service(request: Request) -> CodingAgentService:
    """Resolve the application-scoped service."""
    return request.app.state.coding_agent_service


Service = Annotated[CodingAgentService, Depends(get_service)]


@router.post("", response_model=Run, status_code=202)
async def start_run(body: StartRun, service: Service) -> Run:
    """Submit a coding task and return immediately."""
    return await service.start(body.task, body.source_folder)


@router.get("/{run_id}", response_model=Run)
async def get_run(run_id: str, service: Service) -> Run:
    """Poll status and pending action requests."""
    return service.get(run_id)


@router.get(
    "/{run_id}/events",
    response_class=StreamingResponse,
    responses={
        200: {
            "description": "Replayable status, text, activity, and approval events.",
            "content": {"text/event-stream": {"schema": {"type": "string"}}},
        },
        404: {"description": "Unknown run."},
        409: {"description": "Requested replay history has expired."},
        422: {"description": "Malformed or future event cursor."},
    },
)
async def stream_run(
    run_id: str,
    service: Service,
    last_event_id: Annotated[str | None, Header()] = None,
) -> StreamingResponse:
    """Replay and follow run events; disconnects leave the run active."""
    log = service.event_log(run_id)
    if last_event_id is not None and (
        not last_event_id.isascii()
        or not last_event_id.isdecimal()
        or len(last_event_id) > 20
    ):
        raise InvalidCursor("Last-Event-ID must be a nonnegative integer.")
    cursor = int(last_event_id) if last_event_id is not None else 0
    log.validate_cursor(cursor)

    async def body():
        try:
            async for event in log.subscribe(cursor):
                if event is None:
                    yield ": heartbeat\n\n"
                else:
                    data = json.dumps(
                        {
                            "run_id": event.run_id,
                            "timestamp": event.timestamp,
                            **event.data,
                        },
                        ensure_ascii=False,
                    )
                    yield (
                        f"id: {event.event_id}\nevent: {event.event}\ndata: {data}\n\n"
                    )
        except ReplayExpired:
            yield (
                "event: replay_expired\n"
                'data: {"error":"Replay expired; poll the run for its result."}\n\n'
            )

    return StreamingResponse(
        body(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/resume", response_model=Run, status_code=202)
async def resume_run(run_id: str, body: ResumeRun, service: Service) -> Run:
    """Submit a complete set of approval decisions."""
    return await service.resume(run_id, body)
