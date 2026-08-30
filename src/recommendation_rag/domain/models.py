"""Domain models used by indexing and recommendation workflows."""

from typing import Any

from pydantic import BaseModel, Field


class Product(BaseModel):
    """A catalog item that may be retrieved as recommendation context."""

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    category: str | None = None
    price: float | None = Field(default=None, ge=0)
    attributes: dict[str, Any] = Field(default_factory=dict)

    def to_document_text(self) -> str:
        """Render this product into semantically searchable text."""
        parts = [f"Product: {self.name}", f"Description: {self.description}"]
        if self.category:
            parts.append(f"Category: {self.category}")
        if self.price is not None:
            parts.append(f"Price: {self.price}")
        if self.attributes:
            parts.append(
                "Attributes: "
                + ", ".join(f"{key}: {value}" for key, value in self.attributes.items())
            )
        return "\n".join(parts)

    def to_metadata(self) -> dict[str, str | float]:
        """Return vector-store-safe metadata for this product."""
        metadata: dict[str, str | float] = {"product_id": self.id, "name": self.name}
        if self.category:
            metadata["category"] = self.category
        if self.price is not None:
            metadata["price"] = self.price
        return metadata


class Recommendation(BaseModel):
    """A model-generated recommendation with supporting catalog identity."""

    product_id: str
    name: str
    reason: str


class RecommendationResult(BaseModel):
    """Response returned by the recommendation workflow."""

    answer: str
    recommendations: list[Recommendation]
