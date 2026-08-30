"""Tests for catalog domain serialization behavior."""

from recommendation_rag.domain.models import Product


def test_product_renders_searchable_text_and_metadata() -> None:
    """Products should retain useful fields in document text and metadata."""
    product = Product(
        id="shoe-1",
        name="Trail Runner",
        description="A durable trail shoe.",
        category="footwear",
        price=120,
        attributes={"color": "blue"},
    )

    assert "Trail Runner" in product.to_document_text()
    assert product.to_metadata()["product_id"] == "shoe-1"
