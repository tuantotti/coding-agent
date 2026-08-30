"""Dependency providers that compose infrastructure and application services."""

from functools import lru_cache

from langchain_openai import ChatOpenAI

from recommendation_rag.config import get_settings
from recommendation_rag.indexing.service import CatalogIndexer
from recommendation_rag.infrastructure.vector_store import create_vector_store
from recommendation_rag.retrieval.service import CatalogRetriever
from recommendation_rag.workflows.recommendation import RecommendationWorkflow


@lru_cache
def get_vector_store():
    """Return the singleton persistent vector store for this process."""
    return create_vector_store(get_settings())


def get_indexer() -> CatalogIndexer:
    """Provide the catalog indexing use case."""
    return CatalogIndexer(get_vector_store())


def get_workflow() -> RecommendationWorkflow:
    """Provide the graph-based recommendation use case."""
    settings = get_settings()
    return RecommendationWorkflow(
        retriever=CatalogRetriever(get_vector_store()),
        model=ChatOpenAI(api_key=settings.openai_api_key, model=settings.openai_model),
    )
