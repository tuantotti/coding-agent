"""Request and response schemas for the FastAPI application."""

from pydantic import BaseModel, Field

from recommendation_rag.domain.models import Product, RecommendationResult


class IndexProductsRequest(BaseModel):
    """Payload used to index a batch of catalog products."""

    products: list[Product] = Field(min_length=1)


class IndexProductsResponse(BaseModel):
    """Confirmation returned after catalog indexing."""

    indexed_count: int


class RecommendationRequest(BaseModel):
    """Payload used to request grounded product recommendations."""

    query: str = Field(min_length=3)
    category: str | None = None
    limit: int = Field(default=4, ge=1, le=10)


RecommendationResponse = RecommendationResult
