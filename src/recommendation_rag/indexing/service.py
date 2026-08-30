"""Catalog indexing service responsible for writing product documents."""

from langchain_core.documents import Document

from recommendation_rag.domain.models import Product


class CatalogIndexer:
    """Convert product entities to documents and store their embeddings."""

    def __init__(self, vector_store: object) -> None:
        """Initialize the indexer with a LangChain-compatible vector store."""
        self._vector_store = vector_store

    def index_products(self, products: list[Product]) -> int:
        """Upsert products into the catalog and return the number indexed."""
        documents = [
            Document(
                page_content=product.to_document_text(),
                metadata=product.to_metadata(),
            )
            for product in products
        ]
        if not documents:
            return 0
        self._vector_store.add_documents(
            documents=documents,
            ids=[product.id for product in products],
        )
        return len(documents)
