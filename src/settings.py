"""Environment configuration for the local coding-agent server."""

from pathlib import Path

from pydantic import DirectoryPath, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from agents import AgentSettings


class ServerSettings(BaseSettings):
    """Validate server configuration without creating model clients."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    coding_model: str = Field(default="openai:gpt-5.4", min_length=1)
    coding_workspace_root: DirectoryPath = Field(default_factory=Path.cwd)
    coding_max_remediation_cycles: int = Field(default=2, ge=0)
    coding_shell_timeout_seconds: int = Field(default=120, gt=0)
    openai_api_key: SecretStr = Field(min_length=1)
    tavily_api_key: SecretStr = Field(min_length=1)

    def agent_settings(self) -> AgentSettings:
        """Translate server settings to the existing graph factory contract."""
        return AgentSettings(
            workspace_root=self.coding_workspace_root,
            model=self.coding_model,
            max_remediation_cycles=self.coding_max_remediation_cycles,
            shell_timeout_seconds=self.coding_shell_timeout_seconds,
        )
