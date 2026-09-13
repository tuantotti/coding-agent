"""Optional Langfuse lifecycle and non-destructive callback configuration."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.config import merge_configs

from src.settings import settings


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


def create_tracing() -> LangfuseTracing | None:
    """Initialize Langfuse tracing from application settings."""

    if not settings.langfuse_tracing_enabled:
        return None

    if not settings.langfuse_public_key:
        raise RuntimeError(
            "LANGFUSE_PUBLIC_KEY is required when Langfuse tracing is enabled."
        )

    if not settings.langfuse_secret_key:
        raise RuntimeError(
            "LANGFUSE_SECRET_KEY is required when Langfuse tracing is enabled."
        )

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError as exc:
        raise RuntimeError(
            "Langfuse tracing requires the langfuse dependency; run `uv sync`."
        ) from exc

    client = Langfuse(
        public_key=settings.langfuse_public_key.get_secret_value(),
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=settings.langfuse_base_url,
    )

    return LangfuseTracing(
        client,
        CallbackHandler,
    )


def with_tracing_callback(
    config: RunnableConfig, handler: BaseCallbackHandler, run_id: str
) -> RunnableConfig:
    """Append tracing without replacing existing callbacks or graph settings."""
    return merge_configs(
        config,
        {"callbacks": [handler], "metadata": {"langfuse_session_id": run_id}},
    )
