from langchain_openai import AzureChatOpenAI

from src.settings import settings


def create_azure_model(deployment: str) -> AzureChatOpenAI:
    """Create an Azure OpenAI chat model from application settings."""

    api_key = (
        settings.azure_openai_api_key.get_secret_value()
        if settings.azure_openai_api_key
        else None
    )
    endpoint = settings.azure_openai_endpoint
    api_version = settings.openai_api_version

    return AzureChatOpenAI(
        api_key=api_key,
        azure_endpoint=endpoint,
        api_version=api_version,
        azure_deployment=deployment,
        temperature=0,
        max_retries=3,
    )
