"""LangGraph workflow that retrieves catalog context and generates recommendations."""

from typing import TypedDict

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from recommendation_rag.domain.models import RecommendationResult
from recommendation_rag.retrieval.service import CatalogRetriever


class WorkflowState(TypedDict, total=False):
    """State passed between LangGraph recommendation nodes."""

    query: str
    category: str | None
    limit: int
    documents: list[Document]
    result: RecommendationResult


class GeneratedRecommendation(BaseModel):
    """Structured item emitted by the chat model."""

    product_id: str
    name: str
    reason: str


class GeneratedResponse(BaseModel):
    """Structured response emitted by the chat model."""

    answer: str
    recommendations: list[GeneratedRecommendation] = Field(default_factory=list)


class RecommendationWorkflow:
    """Orchestrate retrieval and grounded recommendation generation with LangGraph."""

    def __init__(self, retriever: CatalogRetriever, model: ChatOpenAI) -> None:
        """Build a workflow that uses the supplied retriever and language model."""
        self._retriever = retriever
        self._structured_model = model.with_structured_output(GeneratedResponse)
        self._graph = self._build_graph()

    def recommend(
        self, query: str, limit: int = 4, category: str | None = None
    ) -> RecommendationResult:
        """Run the retrieval-and-generation graph for one shopper request."""
        state = self._graph.invoke(
            {"query": query, "limit": limit, "category": category}
        )
        return state["result"]

    def _build_graph(self):
        graph = StateGraph(WorkflowState)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("generate", self._generate)
        graph.add_edge(START, "retrieve")
        graph.add_edge("retrieve", "generate")
        graph.add_edge("generate", END)
        return graph.compile()

    def _retrieve(self, state: WorkflowState) -> dict[str, list[Document]]:
        return {
            "documents": self._retriever.retrieve(
                query=state["query"],
                limit=state["limit"],
                category=state.get("category"),
            )
        }

    def _generate(self, state: WorkflowState) -> dict[str, RecommendationResult]:
        context = "\n\n".join(
            f"ID: {document.metadata['product_id']}\n{document.page_content}"
            for document in state["documents"]
        )
        response = self._structured_model.invoke(
            [
                SystemMessage(
                    content=(
                        "Recommend only products in the provided catalog context. "
                        "If nothing fits, say so and return no recommendations."
                    )
                ),
                HumanMessage(
                    content=(
                        f"Shopper request: {state['query']}\n\nCatalog:\n{context}"
                    )
                ),
            ]
        )
        return {"result": RecommendationResult(**response.model_dump())}
