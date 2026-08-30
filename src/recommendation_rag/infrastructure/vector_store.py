"""Factory for the persistent Chroma vector store and OpenAI embeddings."""

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from recommendation_rag.config import Settings


def create_vector_store(settings: Settings) -> Chroma:
    """Create the persistent catalog vector store configured for this application."""
    settings.chroma_persist_directory.mkdir(parents=True, exist_ok=True)
    embeddings = OpenAIEmbeddings(
        api_key=settings.openai_api_key,
        model=settings.openai_embedding_model,
    )
    return Chroma(
        collection_name=settings.collection_name,
        embedding_function=embeddings,
        persist_directory=str(settings.chroma_persist_directory),
    )
