from langchain_openai import AzureChatOpenAI
from loguru import logger

from src.settings import settings


def create_azure_model(
    deployment: str, reasoning_effort: str | None = None
) -> AzureChatOpenAI:
    """Create an Azure OpenAI chat model from application settings."""

    api_key = (
        settings.azure_openai_api_key.get_secret_value()
        if settings.azure_openai_api_key
        else None
    )
    endpoint = settings.azure_openai_endpoint
    api_version = settings.openai_api_version
    # Strip provider prefix e.g. "azure_openai:gpt-4.1-mini" → "gpt-4.1-mini"
    deployment_name = deployment.split(":", 1)[-1]

    if reasoning_effort:
        logger.success(f"Use model={deployment}, reasoning_effort={reasoning_effort}")

        return AzureChatOpenAI(
            temperature=0.0,
            reasoning_effort=reasoning_effort,
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_deployment=deployment_name,
            max_retries=3,
        )
    else:
        # some models like gpt 4.1 do not support params reasoning_effort
        logger.success(f"Use model={deployment}")

        return AzureChatOpenAI(
            temperature=0.0,
            api_key=api_key,
            azure_endpoint=endpoint,
            api_version=api_version,
            azure_deployment=deployment_name,
            max_retries=3,
        )
