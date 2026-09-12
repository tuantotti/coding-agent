"""Run submission, polling, and approval routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from models.runs import ResumeRun, Run, StartRun
from services.coding_agent import CodingAgentService

router = APIRouter(prefix="/v1/runs", tags=["runs"])


def get_service(request: Request) -> CodingAgentService:
    """Resolve the application-scoped service."""
    return request.app.state.coding_agent_service


Service = Annotated[CodingAgentService, Depends(get_service)]


@router.post("", response_model=Run, status_code=202)
async def start_run(body: StartRun, service: Service) -> Run:
    """Submit a coding task and return immediately."""
    return await service.start(body.task)


@router.get("/{run_id}", response_model=Run)
async def get_run(run_id: str, service: Service) -> Run:
    """Poll status and pending action requests."""
    return service.get(run_id)


@router.post("/{run_id}/resume", response_model=Run, status_code=202)
async def resume_run(run_id: str, body: ResumeRun, service: Service) -> Run:
    """Submit a complete set of approval decisions."""
    return await service.resume(run_id, body)
