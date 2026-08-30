"""Catalog retrieval service used during the RAG recommendation phase."""

from langchain_core.documents import Document


class CatalogRetriever:
    """Retrieve the most relevant catalog products for a shopper request."""

    def __init__(self, vector_store: object, default_limit: int = 4) -> None:
        """Initialize the retriever with a compatible vector store."""
        self._vector_store = vector_store
        self._default_limit = default_limit

    def retrieve(
        self, query: str, limit: int | None = None, category: str | None = None
    ) -> list[Document]:
        """Return relevant products, optionally constrained by category."""
        search_kwargs: dict[str, object] = {"k": limit or self._default_limit}
        if category:
            search_kwargs["filter"] = {"category": category}
        return self._vector_store.similarity_search(query, **search_kwargs)
