"""FastAPI application exposing catalog indexing and RAG recommendations."""

from fastapi import Depends, FastAPI, status

from recommendation_rag.api.dependencies import get_indexer, get_workflow
from recommendation_rag.api.schemas import (
    IndexProductsRequest,
    IndexProductsResponse,
    RecommendationRequest,
    RecommendationResponse,
)
from recommendation_rag.indexing.service import CatalogIndexer
from recommendation_rag.workflows.recommendation import RecommendationWorkflow

app = FastAPI(title="RAG Recommendation API", version="0.1.0")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Return a liveness response without initializing model clients."""
    return {"status": "ok"}


@app.post("/v1/index/products", response_model=IndexProductsResponse)
def index_products(
    request: IndexProductsRequest,
    indexer: CatalogIndexer = Depends(get_indexer),
) -> IndexProductsResponse:
    """Embed and persist catalog products for later retrieval."""
    return IndexProductsResponse(indexed_count=indexer.index_products(request.products))


@app.post(
    "/v1/recommendations",
    response_model=RecommendationResponse,
    status_code=status.HTTP_200_OK,
)
def create_recommendations(
    request: RecommendationRequest,
    workflow: RecommendationWorkflow = Depends(get_workflow),
) -> RecommendationResponse:
    """Return catalog-grounded recommendations for a shopper request."""
    return workflow.recommend(request.query, request.limit, request.category)
