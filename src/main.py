"""FastAPI entry point for the trusted local coding-agent API."""

from contextlib import asynccontextmanager
from dataclasses import replace

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agents import create_coding_agent
from routes.runs import router
from services.coding_agent import (
    CodingAgentService,
    InvalidApproval,
    InvalidSourceFolder,
    RunConflict,
    RunNotFound,
)
from services.events import InvalidCursor, ReplayExpired
from settings import ServerSettings


def create_app(
    service: CodingAgentService | None = None,
    settings: ServerSettings | None = None,
) -> FastAPI:
    """Create the app, optionally injecting dependencies for offline tests."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        active_service = service
        if active_service is None:
            config = settings or ServerSettings()
            # LangChain provider integrations read their standard environment keys.
            config.configure_provider_environment()
            base_settings = config.agent_settings()
            active_service = CodingAgentService(
                lambda root: create_coding_agent(
                    replace(base_settings, workspace_root=root, checkpointer=None)
                )
            )
        app.state.coding_agent_service = active_service
        app.state.ready = True
        try:
            yield
        finally:
            app.state.ready = False
            await active_service.close()

    app = FastAPI(title="Coding Agent API", lifespan=lifespan)
    app.state.ready = False
    app.include_router(router)

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
