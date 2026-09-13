"""Environment configuration for the local coding-agent server."""

from functools import lru_cache
from pathlib import Path

from pydantic import DirectoryPath, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    # ------------------------------------------------------------------
    # Application
    # ------------------------------------------------------------------
    app_name: str = Field(default="app", min_length=1)

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    log_level: str = Field(default="debug", min_length=1)
    log_json: bool = False
    log_dir: Path = Path("logs")

    # ------------------------------------------------------------------
    # Azure OpenAI
    # ------------------------------------------------------------------
    azure_openai_api_key: SecretStr | None = None
    azure_openai_endpoint: str | None = None
    openai_api_version: str | None = None

    # ------------------------------------------------------------------
    # Coding Agent
    # ------------------------------------------------------------------
    coding_model: str = Field(
        default="gpt-5.4-nano",
        min_length=1,
    )
    coding_workspace_root: DirectoryPath = Field(
        default_factory=Path.cwd,
    )
    coding_max_remediation_cycles: int = Field(
        default=2,
        ge=0,
    )
    coding_shell_timeout_seconds: int = Field(
        default=120,
        gt=0,
    )

    # ------------------------------------------------------------------
    # LangSmith
    # ------------------------------------------------------------------
    langsmith_tracing: bool = False
    langsmith_endpoint: str | None = None
    langsmith_api_key: SecretStr | None = None
    langsmith_project: str | None = None

    # ------------------------------------------------------------------
    # Langfuse
    # ------------------------------------------------------------------
    langfuse_tracing_enabled: bool = False
    langfuse_public_key: SecretStr | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_base_url: str = Field(
        default="https://cloud.langfuse.com",
        min_length=1,
    )

    # ------------------------------------------------------------------
    # Tavily
    # ------------------------------------------------------------------
    tavily_api_key: SecretStr = Field(min_length=1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the cached application settings."""
    return Settings()


settings = get_settings()
