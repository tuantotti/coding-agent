"""FastAPI entry point for the trusted local coding-agent API."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from agents import create_coding_agent
from routes.runs import router
from services.coding_agent import (
    CodingAgentService,
    InvalidApproval,
    RunConflict,
    RunNotFound,
)
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
            os.environ["OPENAI_API_KEY"] = config.openai_api_key.get_secret_value()
            os.environ["TAVILY_API_KEY"] = config.tavily_api_key.get_secret_value()
            active_service = CodingAgentService(
                create_coding_agent(config.agent_settings())
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
        status = {RunNotFound: 404, RunConflict: 409, InvalidApproval: 422}[type(exc)]
        return JSONResponse({"detail": str(exc)}, status_code=status)

    for exception in (RunNotFound, RunConflict, InvalidApproval):
        app.add_exception_handler(exception, service_error)
    return app


app = create_app()
