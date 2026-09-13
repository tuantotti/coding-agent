"""Optional Langfuse lifecycle and non-destructive callback configuration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs

from src.settings import ServerSettings


class TracingClient(Protocol):
    """The SDK lifecycle operation needed by the server."""

    def shutdown(self) -> None:
        """Flush queued observations and stop export workers."""
        ...


@dataclass(frozen=True)
class LangfuseTracing:
    """Own the client and create an independent callback per execution."""

    client: TracingClient
    callback_factory: Callable[[], BaseCallbackHandler]

    async def close(self) -> None:
        """Flush outside the event loop after agent jobs have stopped."""
        await asyncio.to_thread(self.client.shutdown)


def create_tracing(settings: ServerSettings) -> LangfuseTracing | None:
    """Initialize the SDK at startup using the configured environment."""
    if not settings.langfuse_tracing_enabled:
        return None
    try:
        from langfuse import get_client
        from langfuse.langchain import CallbackHandler
    except ImportError as exc:
        raise RuntimeError(
            "Langfuse tracing requires the langfuse dependency; run uv sync."
        ) from exc
    return LangfuseTracing(get_client(), CallbackHandler)


def with_tracing_callback(
    config: RunnableConfig, handler: BaseCallbackHandler, run_id: str
) -> RunnableConfig:
    """Append tracing without replacing existing callbacks or graph settings."""
    return merge_configs(
        config,
        {"callbacks": [handler], "metadata": {"langfuse_session_id": run_id}},
    )
