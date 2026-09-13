"""Environment configuration for the local coding-agent server."""

import os
from pathlib import Path
from typing import Self

from pydantic import DirectoryPath, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.agents import AgentSettings


class ServerSettings(BaseSettings):
    """Validate server configuration without creating model clients."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    coding_model: str = Field(default="openai:gpt-5.4", min_length=1)
    coding_workspace_root: DirectoryPath = Field(default_factory=Path.cwd)
    coding_max_remediation_cycles: int = Field(default=2, ge=0)
    coding_shell_timeout_seconds: int = Field(default=120, gt=0)
    tavily_api_key: SecretStr = Field(min_length=1)
    openai_api_key: SecretStr | None = None
    azure_openai_api_key: SecretStr | None = None
    azure_openai_endpoint: str | None = None
    openai_api_version: str | None = None
    langsmith_tracing: bool = False
    langsmith_endpoint: str | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str | None = None
    langfuse_tracing_enabled: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = Field(default="https://cloud.langfuse.com", min_length=1)

    @model_validator(mode="after")
    def validate_tracing_credentials(self) -> Self:
        """Require nonblank credentials only when tracing is enabled."""
        if self.langfuse_tracing_enabled:
            for name in ("langfuse_public_key", "langfuse_secret_key"):
                value = getattr(self, name)
                if value is None or not value.get_secret_value().strip():
                    raise ValueError(f"{name.upper()} is required for Langfuse tracing")
        return self

    def configure_provider_environment(self) -> None:
        """Expose resolved provider settings to LangChain and LangSmith SDKs.

        Call once at application startup. Pydantic loads dotenv values into
        this instance but does not populate the process environment itself.
        """
        for name in (
            "openai_api_key",
            "azure_openai_api_key",
            "azure_openai_endpoint",
            "openai_api_version",
            "tavily_api_key",
            "langsmith_tracing",
            "langsmith_endpoint",
            "langsmith_api_key",
            "langsmith_project",
            "langfuse_tracing_enabled",
            "langfuse_public_key",
            "langfuse_secret_key",
            "langfuse_base_url",
        ):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            elif isinstance(value, bool):
                value = str(value).lower()
            os.environ[name.upper()] = value

    def agent_settings(self) -> AgentSettings:
        """Translate server settings to the existing graph factory contract."""
        return AgentSettings(
            workspace_root=self.coding_workspace_root,
            model=self.coding_model,
            max_remediation_cycles=self.coding_max_remediation_cycles,
            shell_timeout_seconds=self.coding_shell_timeout_seconds,
        )
