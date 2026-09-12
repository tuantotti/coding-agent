"""A small, predictable Tavily adapter for the research subagent."""

import json
import os
from collections.abc import Mapping, Sequence
from typing import Any

from langchain_core.tools import StructuredTool


class TavilyConfigurationError(RuntimeError):
    """Raised when web research is requested without Tavily credentials."""


def normalize_tavily_results(response: Any) -> list[dict[str, str]]:
    """Extract citation-ready title, URL, and content fields from Tavily output."""
    results = response.get("results", []) if isinstance(response, Mapping) else response
    if not isinstance(results, Sequence) or isinstance(results, str):
        return []
    normalized: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, Mapping):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        title = item.get("title")
        content = item.get("content") or item.get("raw_content")
        normalized.append(
            {
                "title": title if isinstance(title, str) else url,
                "url": url,
                "content": content if isinstance(content, str) else "",
            }
        )
    return normalized


def _make_tavily_search(max_results: int) -> Any:
    try:
        from langchain_tavily import TavilySearch
    except ImportError as exc:  # pragma: no cover
        raise TavilyConfigurationError(
            "Tavily support is unavailable. Install the langchain-tavily dependency."
        ) from exc
    return TavilySearch(max_results=max_results)


def create_tavily_search_tool(max_results: int = 5) -> StructuredTool:
    """Create the research tool, failing early when Tavily is not configured."""
    if not os.getenv("TAVILY_API_KEY"):
        raise TavilyConfigurationError(
            "TAVILY_API_KEY is required to create the information-retrieval agent."
        )
    search = _make_tavily_search(max_results)

    def search_web(query: str) -> str:
        """Search the web and return concise results with source URLs."""
        response = search.invoke({"query": query})
        return json.dumps(normalize_tavily_results(response), ensure_ascii=False)

    return StructuredTool.from_function(
        func=search_web,
        name="search_web",
        description="Search technical information and return cited web results.",
    )
