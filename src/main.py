"""FastAPI entry point for the trusted local coding-agent API."""

from contextlib import asynccontextmanager
from dataclasses import replace

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from src.agents import AgentSettings, create_coding_agent
from src.logger import configure_logging
from src.routes.runs import router
from src.routes.system import system_router
from src.services.coding_agent import (
    CodingAgentService,
    InvalidApproval,
    InvalidSourceFolder,
    RunConflict,
    RunNotFound,
)
from src.services.events import InvalidCursor, ReplayExpired
from src.services.tracing import create_tracing
from src.settings import settings

configure_logging(
    log_level=settings.log_level,
    json_logs=settings.log_json,
)


def create_app(
    service: CodingAgentService | None = None,
) -> FastAPI:
    """Create the app, optionally injecting dependencies for offline tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_service = service
        tracing = None
        if active_service is None:
            tracing = create_tracing()
            agent_settings = AgentSettings(
                workspace_root=settings.coding_workspace_root,
                model=settings.coding_model,
                max_remediation_cycles=settings.coding_max_remediation_cycles,
                shell_timeout_seconds=settings.coding_shell_timeout_seconds,
            )
            active_service = CodingAgentService(
                lambda root: create_coding_agent(
                    settings=replace(agent_settings, workspace_root=root)
                ),
                callback_factory=tracing.callback_factory if tracing else None,
            )
        app.state.coding_agent_service = active_service
        app.state.ready = True
        logger.info("Coding agent application startup completed")
        try:
            yield
        finally:
            app.state.ready = False
            logger.info("Coding agent application shutdown started")
            try:
                await active_service.close()
            finally:
                if tracing is not None:
                    await tracing.close()
                logger.info("Coding agent application shutdown completed")

    app = FastAPI(title="Coding Agent API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.ready = False
    app.include_router(router)
    app.include_router(system_router)

    @app.get("/health")
    async def health() -> JSONResponse:
        """Report readiness without calling external providers."""
        return JSONResponse(
            {"status": "ready" if app.state.ready else "unavailable"},
            status_code=200 if app.state.ready else 503,
        )

    async def service_error(request: Request, exc: Exception) -> JSONResponse:
        status = {
            RunNotFound: 404,
            RunConflict: 409,
            InvalidApproval: 422,
            InvalidSourceFolder: 422,
            InvalidCursor: 422,
            ReplayExpired: 409,
        }[type(exc)]
        return JSONResponse({"detail": str(exc)}, status_code=status)

    for exception in (
        RunNotFound,
        RunConflict,
        InvalidApproval,
        InvalidSourceFolder,
        InvalidCursor,
        ReplayExpired,
    ):
        app.add_exception_handler(exception, service_error)
    return app


app = create_app()


def main() -> None:
    """Run the trusted local API using package-qualified imports."""
    uvicorn.run("src.main:app", host="127.0.0.1", port=8000, workers=1)


if __name__ == "__main__":
    main()
